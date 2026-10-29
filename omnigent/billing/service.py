"""Plan authorization and SDK-free payment/provider transport."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import math
import os
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from dateutil.relativedelta import relativedelta
from fastapi import HTTPException
from starlette.responses import StreamingResponse

from omnigent.billing.config import BillingConfig, Model, Plan, Provider
from omnigent.billing.failover import FreeFailover, ProviderFailure, _zero_cost
from omnigent.billing.queue import InferenceQueue
from omnigent.billing.store import BillingStore


def _provider_rejection(response: httpx.Response) -> HTTPException:
    if response.status_code in {429, 503}:
        raw = response.headers.get("retry-after", "60")
        delay = min(3600, max(1, int(raw))) if raw.isdigit() else 60
        return ProviderFailure(
            response.status_code,
            "Model capacity is temporarily limited; retry after the indicated delay.",
            headers={"Retry-After": str(delay)},
        )
    if response.status_code in {401, 402, 403, 404, 408} or response.status_code >= 500:
        return ProviderFailure(502, "Model provider is temporarily unavailable")
    # Validation failures will not improve with retries. Preserve their class
    # so SDK clients do not multiply the gateway's own retry budget.
    status = response.status_code if response.status_code in {400, 413, 422} else 502
    return HTTPException(status, f"Model provider rejected the request ({response.status_code})")


class BillingService:
    def __init__(
        self,
        config: BillingConfig,
        store: BillingStore,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.config, self.store, self.transport = config, store, transport
        self.queue = InferenceQueue(config.max_inflight, config.queue_limit)
        self.checkout_lock = asyncio.Lock()
        self.webhook_lock = asyncio.Lock()
        self.free_router = FreeFailover(config)

    def provider_model(self, identifier: str) -> tuple[Provider, Model]:
        provider_id, _, model_id = identifier.partition("/")
        for provider in self.config.providers:
            if provider.id == provider_id:
                for model in provider.models:
                    if model.id == model_id:
                        return provider, model
        raise HTTPException(400, "Select a configured provider/model")

    def entitlement(self, owner: str) -> dict[str, Any]:
        account = self.store.account(owner)
        if account.get("subscription"):
            return account
        membership = self.store.membership(owner)
        if membership and membership["accepted"]:
            team = self.store.account(membership["team"])
            roster = self.store.members(membership["team"])
            assigned = [m["member"] for m in roster][: max(0, team.get("seats", 1) - 1)]
            if owner in assigned:
                return {**team, "team_owner": membership["team"]}
        return account

    def plan_period(self, owner: str, mode: str) -> tuple[Plan, str]:
        account = self.entitlement(owner)
        now = time.time()
        active = (
            account.get("status") in {"active", "trialing"} and account.get("period_end", 0) > now
        )
        plan_id = account.get("plan") if active and mode == "managed" else "free"
        if mode == "managed" and not active:
            raise HTTPException(402, "An active Xwav subscription is required for managed models")
        plan = next((p for p in self.config.plans if p.id == plan_id), None)
        if plan is None:
            raise HTTPException(503, "Subscription plan is no longer configured")
        period = self.period(account) if mode == "managed" else datetime.now(UTC).strftime("%Y-%m")
        return plan, period

    def period(self, account: dict[str, Any], offset: int = 0) -> str:
        now = datetime.now(UTC)
        start = datetime.fromtimestamp(account["period_start"], UTC)
        months = max(0, (now.year - start.year) * 12 + now.month - start.month)
        if start + relativedelta(months=months) > now:
            months -= 1
        boundary = start + relativedelta(months=months + offset)
        return (
            str(account.get("team_owner", account.get("customer", "self")))
            + "|"
            + boundary.isoformat()
        )

    def token_allowance(self, owner: str, mode: str, plan: Plan) -> int:
        if mode != "managed" or not plan.rollover:
            return plan.token_limit
        account = self.entitlement(owner)
        previous = self.period(account, -1)
        previous_date = datetime.fromisoformat(previous.rsplit("|", 1)[1])
        if previous_date.timestamp() < float(
            account.get("entitlement_start") or account["period_start"]
        ):
            return plan.token_limit
        usage = self.store.usage(owner, previous, mode)
        return plan.token_limit + max(0, plan.token_limit - usage["tokens"])

    def status(self, owner: str) -> dict[str, Any]:
        account = self.store.account(owner)
        mode = account.get("mode", "free")
        try:
            plan, period = self.plan_period(owner, mode)
        except HTTPException:
            mode = "free"
            plan, period = self.plan_period(owner, mode)
        entitlement = self.entitlement(owner)
        try:
            subscribed_plan, _ = self.plan_period(owner, "managed")
        except HTTPException:
            subscribed_plan = next(p for p in self.config.plans if p.id == "free")
        return {
            "enabled": True,
            "free_failover": self.config.free_failover,
            "plan": subscribed_plan.id,
            "mode": mode,
            "model": account.get("model", ""),
            "status": entitlement.get("status", "free"),
            "period_end": account.get("period_end"),
            "period": period,
            "usage": self.store.usage(owner, period, mode),
            "included_micro_usd": plan.included_micro_usd,
            "allowance_mode": "tokens" if plan.token_limit else "credits",
            "request_limit": self.config.byok_request_limit
            if mode == "byok"
            else plan.request_limit,
            "keys": self.store.key_ids(owner),
            "has_gateway_token": bool(account.get("token_hash")),
            "checkout_enabled": bool(os.getenv("XWAV_STRIPE_SECRET_KEY")),
            "portal_enabled": bool(account.get("customer")),
            "team": self.store.membership(owner),
            "members": self.store.members(owner),
            "seats": account.get("seats", 1),
            "included_credits": plan.included_credits,
            "credits_used": (
                self.store.usage(owner, period, mode)["spent_micro_usd"]
                * plan.included_credits
                / plan.included_micro_usd
            )
            if plan.included_credits and plan.included_micro_usd
            else None,
            "token_allowance": self.token_allowance(owner, mode, plan),
            "plans": [
                {
                    "id": p.id,
                    "label": p.label,
                    "monthly_usd": p.monthly_usd,
                    "annual_monthly_usd": p.annual_monthly_usd,
                    "token_limit": p.token_limit,
                    "rollover": p.rollover,
                    "included_micro_usd": p.included_micro_usd,
                    "request_limit": p.request_limit,
                    "included_credits": p.included_credits,
                    "per_seat": p.per_seat,
                    "purchasable": bool(
                        p.stripe_price_env
                        and os.getenv(p.stripe_price_env)
                        and (p.token_limit or p.included_micro_usd)
                    ),
                }
                for p in self.config.plans
            ],
            "providers": [
                {
                    "id": p.id,
                    "label": p.label,
                    "managed_ready": bool(os.getenv(p.api_key_env)),
                    "models": [m.model_dump() for m in p.models],
                }
                for p in self.config.providers
            ],
        }

    async def stripe(
        self,
        method: str,
        path: str,
        data: dict[str, str] | None = None,
        idempotency: str | None = None,
    ) -> dict[str, Any]:
        key = os.getenv("XWAV_STRIPE_SECRET_KEY")
        if not key:
            raise HTTPException(503, "Stripe is not configured")
        if key.startswith("sk_live_") and os.getenv("XWAV_BILLING_LIVE") != "1":
            raise HTTPException(
                503, "Live billing requires XWAV_BILLING_LIVE=1; use Stripe test keys first"
            )
        headers = {"Authorization": f"Bearer {key}"}
        if idempotency:
            headers["Idempotency-Key"] = idempotency
        async with httpx.AsyncClient(transport=self.transport, timeout=30) as client:
            try:
                response = await client.request(
                    method, f"https://api.stripe.com/v1/{path}", data=data, headers=headers
                )
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError):
                raise HTTPException(
                    502, "Payment service unavailable; no subscription change confirmed"
                ) from None

    async def checkout(
        self, owner: str, plan_id: str, seats: int = 1, annual: bool = False
    ) -> dict[str, str]:
        async with self.checkout_lock:
            return await self._checkout(owner, plan_id, seats, annual)

    async def _checkout(
        self, owner: str, plan_id: str, seats: int = 1, annual: bool = False
    ) -> dict[str, str]:
        plan = next((p for p in self.config.plans if p.id == plan_id and p.monthly_usd), None)
        if plan is None:
            raise HTTPException(400, "Unknown paid plan")
        price = (
            os.getenv(plan.annual_stripe_price_env if annual else plan.stripe_price_env)
            if plan
            else None
        )
        if plan and not (plan.token_limit or plan.included_micro_usd):
            raise HTTPException(400, "Configure this plan allowance before enabling checkout")
        if not price:
            raise HTTPException(400, "This plan is not configured for checkout")
        if seats != 1 and (plan is None or not plan.per_seat):
            raise HTTPException(400, "Only Teams supports multiple seats")
        if annual and not plan.annual_monthly_usd:
            raise HTTPException(400, "This plan has no annual price")
        price_details = await self.stripe("GET", f"prices/{price}")
        expected = (
            (plan.annual_monthly_usd or plan.monthly_usd) * 12 if annual else plan.monthly_usd
        ) * 100
        interval = "year" if annual else "month"
        recurring = price_details.get("recurring") or {}
        if (
            price_details.get("currency") != "usd"
            or price_details.get("unit_amount") != expected
            or not price_details.get("active")
            or recurring.get("interval") != interval
            or recurring.get("interval_count", 1) != 1
        ):
            raise HTTPException(503, "Stripe price does not match this plan; contact the operator")
        account = self.store.account(owner)
        if account.get("subscription"):
            raise HTTPException(409, "Manage your existing subscription in the billing portal")
        pending = account.get("checkout")
        selection = f"{plan_id}:{seats}:{annual}"
        if pending and pending["expires"] > time.time():
            if pending["selection"] == selection:
                return {"url": pending["url"]}
            await self.stripe("POST", f"checkout/sessions/{pending['id']}/expire")
        # Stripe idempotency protects transport retries as well as local serialization.
        fingerprint = [
            owner,
            plan_id,
            seats,
            annual,
            account.get("status", "free"),
            account.get("subscription_created", 0),
            int(time.time()) // 600,
        ]
        checkout_id = hashlib.sha256(json.dumps(fingerprint).encode()).hexdigest()

        result = await self.stripe(
            "POST",
            "checkout/sessions",
            {
                "mode": "subscription",
                "expires_at": str(int(time.time()) + 1800),
                "line_items[0][price]": price,
                "line_items[0][quantity]": str(seats),
                "client_reference_id": owner,
                "subscription_data[metadata][xwav_owner]": owner,
                "success_url": self.config.public_url.rstrip("/")
                + "/settings/billing?checkout=success",
                "cancel_url": self.config.public_url.rstrip("/")
                + "/settings/billing?checkout=cancelled",
            },
            checkout_id,
        )
        if result.get("id"):
            self.store.update(
                owner,
                checkout={
                    "id": result["id"],
                    "url": result["url"],
                    "selection": selection,
                    "expires": result.get("expires_at", time.time() + 1800),
                },
            )
        return {"url": result["url"]}

    async def portal(self, owner: str) -> dict[str, str]:
        customer = self.store.account(owner).get("customer")
        if not customer:
            raise HTTPException(400, "No billing customer is connected")
        result = await self.stripe(
            "POST",
            "billing_portal/sessions",
            {
                "customer": customer,
                "return_url": self.config.public_url.rstrip("/") + "/settings/billing",
            },
        )
        return {"url": result["url"]}

    async def webhook(self, raw: bytes, signature: str) -> None:
        async with self.webhook_lock:
            await self._webhook(raw, signature)

    async def _webhook(self, raw: bytes, signature: str) -> None:
        secret = os.getenv("XWAV_STRIPE_WEBHOOK_SECRET", "")
        parts: dict[str, list[str]] = {}
        for item in signature.split(","):
            name, _, value = item.partition("=")
            parts.setdefault(name, []).append(value)
        try:
            timestamp = parts["t"][0]
            valid_time = abs(time.time() - int(timestamp)) <= 300
        except (KeyError, ValueError):
            raise HTTPException(400, "Invalid payment signature") from None
        digest = hmac.new(
            secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256
        ).hexdigest()
        if (
            not secret
            or not valid_time
            or not any(hmac.compare_digest(digest, s) for s in parts.get("v1", []))
        ):
            raise HTTPException(400, "Invalid payment signature")
        try:
            event = json.loads(raw)
            kind, obj = event["type"], event["data"]["object"]
            subscription_id = (
                obj.get("subscription") if kind == "checkout.session.completed" else obj.get("id")
            )
            if kind not in {
                "checkout.session.completed",
                "customer.subscription.created",
                "customer.subscription.updated",
                "customer.subscription.deleted",
            }:
                return
            if (
                not isinstance(subscription_id, str)
                or not subscription_id.startswith("sub_")
                or not subscription_id.replace("_", "").isalnum()
            ):
                raise ValueError
            # Fetch authoritative state: delayed/replayed events cannot reactivate an old plan.
            current = await self.stripe("GET", f"subscriptions/{subscription_id}")
            owner = current["metadata"]["xwav_owner"]
            item = current["items"]["data"][0]
            plan = next(
                (
                    p
                    for p in self.config.plans
                    if p.monthly_usd
                    and item["price"]["id"]
                    in {os.getenv(p.stripe_price_env), os.getenv(p.annual_stripe_price_env)}
                ),
                None,
            )

            active = current["status"] in {"active", "trialing"} and plan is not None
            self.store.event(
                event["id"],
                owner,
                {
                    "plan": plan.id if active else "free",
                    "entitlement_start": current.get("start_date", current.get("created", 0)),
                    "subscription_created": current.get("created", 0),
                    "checkout": None,
                    "status": current["status"],
                    "customer": current["customer"],
                    "seats": item.get("quantity", 1) if plan and plan.per_seat else 1,
                    "subscription": None
                    if current["status"] in {"canceled", "incomplete_expired"}
                    else current["id"],
                    "period_start": item.get(
                        "current_period_start", current.get("current_period_start", 0)
                    ),
                    "period_end": item.get(
                        "current_period_end", current.get("current_period_end", 0)
                    ),
                },
            )
        except (KeyError, ValueError, TypeError, IndexError):
            raise HTTPException(400, "Unsupported payment event data") from None

    async def infer(self, owner: str, mode: str, protocol: str, body: dict[str, Any]) -> Any:
        try:
            self.plan_period(owner, "managed")
            paid = True
        except HTTPException:
            paid = False
        await self.queue.acquire(paid)
        streaming = False
        try:
            selected = self.provider_model(body.get("model", ""))
            if (
                mode in {"free", "managed"}
                and self.config.free_failover
                and _zero_cost(selected[1])
            ):
                self.plan_period(owner, mode)
                result = await self.free_router.infer(
                    selected,
                    protocol,
                    body,
                    lambda payload, charge: self._infer(
                        owner, mode, protocol, payload, charge_request=charge
                    ),
                    lambda provider: bool(os.getenv(provider.api_key_env)),
                )
            else:
                result = await self._infer(owner, mode, protocol, body)
            if isinstance(result, StreamingResponse):
                iterator = result.body_iterator

                async def queued_stream():
                    try:
                        async for chunk in iterator:
                            yield chunk
                    finally:
                        await self.queue.release()

                result.body_iterator = queued_stream()
                streaming = True
            return result
        finally:
            if not streaming:
                await self.queue.release()

    async def _infer(
        self,
        owner: str,
        mode: str,
        protocol: str,
        body: dict[str, Any],
        *,
        charge_request: bool = True,
    ) -> Any:
        if mode not in {"free", "managed", "byok"}:
            raise HTTPException(400, "Unknown usage mode")
        provider, model = self.provider_model(body.get("model", ""))
        if model.protocol != protocol and protocol not in provider.compatible_protocols:
            raise HTTPException(400, "This model requires a different harness API protocol")
        plan, period = self.plan_period(owner, mode)
        if mode == "free" and not model.free:
            raise HTTPException(403, "This model is not offered on the Free plan")
        key = (
            self.store.key(owner, provider.id)
            if mode == "byok"
            else os.getenv(provider.api_key_env)
        )
        if not key:
            raise HTTPException(503, "Selected provider credential is not configured")
        # Count all serialized input bytes as tokens for conservative reservation.
        # Bill at configured rates after usage is returned; no cost-estimation model call.
        output_field = model.output_token_field or (
            "max_output_tokens"
            if protocol == "responses"
            else "max_completion_tokens"
            if protocol == "chat/completions" and "max_completion_tokens" in body
            else "max_tokens"
        )
        requested = next(
            (
                body[k]
                for k in (output_field, "max_tokens", "max_completion_tokens", "max_output_tokens")
                if k in body
            ),
            model.max_output_tokens,
        )

        if type(requested) is not int or not 1 <= requested <= model.max_output_tokens:
            raise HTTPException(400, "Output token limit exceeds this model's configured maximum")
        payload = {**body, "model": model.upstream, output_field: requested, "stream": False}
        for field in ("max_tokens", "max_completion_tokens", "max_output_tokens"):
            if field != output_field:
                payload.pop(field, None)
        payload.pop("stream_options", None)
        if provider.omit_parallel_tool_calls:
            # Some compatible endpoints reject even an explicit false hint.
            payload.pop("parallel_tool_calls", None)
        # Prevent client references from reusing state/assets billed outside this reservation.
        if any(k in payload for k in ("previous_response_id", "conversation", "background", "n")):
            raise HTTPException(
                400, "Stateful/background/multiple-output requests are not supported"
            )
        serialized = json.dumps(payload).encode()

        def forbidden_content(value: Any) -> bool:
            if isinstance(value, dict):
                if any(
                    k in value
                    for k in {
                        "image_url",
                        "image",
                        "input_audio",
                        "audio",
                        "video",
                        "file_id",
                        "file_data",
                        "source",
                    }
                ):
                    return True
                return any(forbidden_content(v) for v in value.values())
            return isinstance(value, list) and any(forbidden_content(v) for v in value)

        tools = payload.get("tools") or []
        if not isinstance(tools, list):
            raise HTTPException(400, "tools must be a list")
        builtins = any(
            not isinstance(t, dict) or t.get("type", "function") != "function" for t in tools
        )
        if mode != "byok" and (
            forbidden_content({key: value for key, value in payload.items() if key != "tools"})
            or builtins
            or payload.get("modalities", ["text"]) != ["text"]
        ):
            raise HTTPException(
                400, "Managed billing supports text and client-executed function tools only"
            )

        reserved = (
            0
            if mode == "byok"
            else math.ceil(
                len(serialized) * model.input_usd_per_million * 2
                + requested * model.output_usd_per_million
            )
        )
        reserved_tokens = 0 if mode == "byok" else len(serialized) + requested
        if not charge_request and (mode not in {"free", "managed"} or not _zero_cost(model)):
            raise HTTPException(400, "Only zero-cost Free retries may reuse reservations")
        self.store.reserve(
            owner,
            period,
            mode,
            reserved,
            None if mode == "byok" or plan.token_limit else plan.included_micro_usd,
            self.config.byok_request_limit if mode == "byok" else plan.request_limit,
            reserved_tokens,
            0 if mode == "byok" else self.token_allowance(owner, mode, plan),
            count_request=charge_request,
        )
        headers = {"Authorization": f"Bearer {key}"}
        if protocol == "messages":
            headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        if body.get("stream") is True:
            payload["stream"] = True
            if protocol == "chat/completions":
                payload["stream_options"] = {"include_usage": True}
            return await self.stream(
                owner,
                period,
                mode,
                reserved,
                reserved_tokens,
                provider,
                model,
                protocol,
                payload,
                headers,
            )
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=180) as client:
                response = await client.post(
                    provider.base_url.rstrip("/") + "/" + protocol, json=payload, headers=headers
                )
            if response.status_code >= 400:
                # Rejected requests incur no model usage. Never expose upstream bodies or headers.
                self.store.settle(owner, period, mode, reserved, 0, reserved_tokens, 0)
                raise _provider_rejection(response)
            if mode in {"free", "managed"}:
                self.free_router.observe(provider, model, protocol, response.headers)
            result = response.json()
        except (httpx.HTTPError, ValueError):
            # Unknown outcome keeps its reservation; operators may reconcile the provider bill.
            raise ProviderFailure(
                502,
                "Model provider unavailable; usage reservation retained pending reconciliation",
            ) from None
        usage = result.get("usage", {})
        input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
        output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
        if (
            mode != "byok"
            and type(input_tokens) is int
            and type(output_tokens) is int
            and min(input_tokens, output_tokens) >= 0
        ):
            actual = math.ceil(
                (
                    input_tokens
                    + usage.get("cache_creation_input_tokens", 0) * 2
                    + usage.get("cache_read_input_tokens", 0)
                )
                * model.input_usd_per_million
                + output_tokens * model.output_usd_per_million
            )
            self.store.settle(
                owner,
                period,
                mode,
                reserved,
                actual,
                reserved_tokens,
                input_tokens + output_tokens,
            )
        return result

    async def stream(
        self,
        owner: str,
        period: str,
        mode: str,
        reserved: int,
        reserved_tokens: int,
        provider: Provider,
        model: Model,
        protocol: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> StreamingResponse:
        client = httpx.AsyncClient(transport=self.transport, timeout=180)
        try:
            response = await client.send(
                client.build_request(
                    "POST",
                    provider.base_url.rstrip("/") + "/" + protocol,
                    json=payload,
                    headers=headers,
                ),
                stream=True,
            )
        except BaseException as error:
            await client.aclose()
            if isinstance(error, httpx.HTTPError):
                raise ProviderFailure(
                    502, "Provider stream unavailable; reservation retained"
                ) from None
            raise
        if response.status_code >= 400:
            await response.aclose()
            await client.aclose()
            self.store.settle(owner, period, mode, reserved, 0, reserved_tokens, 0)
            raise _provider_rejection(response)
        if mode in {"free", "managed"}:
            self.free_router.observe(provider, model, protocol, response.headers)

        async def chunks():
            usage: dict[str, Any] = {}
            buffer = ""
            complete = False
            try:
                async for chunk in response.aiter_text():
                    buffer += chunk
                    if len(buffer) > 2_000_000:
                        raise RuntimeError("Oversized provider stream event")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        if not line.startswith("data: "):
                            continue
                        data = line[6:].strip()
                        if data == "[DONE]":
                            complete = True
                            continue
                        try:
                            event = json.loads(data)
                        except ValueError:
                            continue
                        usage.update(
                            event.get("usage")
                            or event.get("message", {}).get("usage")
                            or event.get("response", {}).get("usage")
                            or {}
                        )
                        if event.get("type") in {"message_stop", "response.completed"}:
                            complete = True
                    yield chunk
                input_count = usage.get("input_tokens", usage.get("prompt_tokens"))
                output_count = usage.get("output_tokens", usage.get("completion_tokens"))
                if (
                    complete
                    and mode != "byok"
                    and type(input_count) is int
                    and type(output_count) is int
                ):
                    actual = math.ceil(
                        (
                            input_count
                            + usage.get("cache_creation_input_tokens", 0) * 2
                            + usage.get("cache_read_input_tokens", 0)
                        )
                        * model.input_usd_per_million
                        + output_count * model.output_usd_per_million
                    )
                    self.store.settle(
                        owner,
                        period,
                        mode,
                        reserved,
                        actual,
                        reserved_tokens,
                        input_count + output_count,
                    )
            finally:
                await response.aclose()
                await client.aclose()

        return StreamingResponse(
            chunks(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

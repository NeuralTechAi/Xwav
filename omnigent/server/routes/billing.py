"""Authenticated subscription settings and scoped model gateway endpoints."""

from __future__ import annotations

import asyncio
import io
import json
import tarfile
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, SecretStr

from omnigent.billing.responses_tools import ResponsesToolBridge
from omnigent.billing.service import BillingService
from omnigent.server.auth import RESERVED_USER_LOCAL, AuthProvider
from omnigent.server.routes._auth_helpers import require_user


class Selection(BaseModel):
    mode: Literal["free", "managed", "byok"]
    model: str = Field(max_length=250)


class KeyInput(BaseModel):
    key: SecretStr


class CheckoutInput(BaseModel):
    plan: str = Field(max_length=32)
    seats: int = Field(default=1, ge=1, le=10000)
    annual: bool = False


class MemberInput(BaseModel):
    member: str = Field(min_length=1, max_length=254)


async def bounded_body(request: Request) -> bytes:
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 2_000_000:
            raise HTTPException(413, "Request exceeds the 2 MB gateway limit")
    return bytes(data)


def create_billing_router(
    service: BillingService | None, auth_provider: AuthProvider | None = None
) -> APIRouter:
    router = APIRouter()

    def available() -> BillingService:
        if service is None:
            raise HTTPException(
                503, "Billing gateway needs operator configuration; see docs/SUBSCRIPTIONS.md"
            )
        return service

    async def inference_owner(request: Request, mode: str) -> tuple[str, bool]:
        svc = available()
        value = request.headers.get("authorization", "").removeprefix(
            "Bearer "
        ) or request.headers.get("x-api-key", "")
        if value.startswith("xwav_scan_"):
            from omnigent.server.strix_jobs import scan_identity

            return await asyncio.to_thread(scan_identity, svc, value, mode), True
        if value.startswith("xwav_job_"):
            from omnigent.billing.jobs import job_identity

            identity = await asyncio.to_thread(
                job_identity, svc, getattr(request.app.state, "host_store", None), value, mode
            )
            return identity, True
        if not value.startswith("xwav_"):
            raise HTTPException(401, "Xwav gateway token required")
        return await asyncio.to_thread(svc.store.token_owner, value), False

    def owner(request: Request) -> str:
        identity = require_user(request, auth_provider) or RESERVED_USER_LOCAL
        if (
            identity == RESERVED_USER_LOCAL
            and service is not None
            and urlsplit(service.config.public_url).hostname
            not in {"localhost", "127.0.0.1", "::1"}
        ):
            raise HTTPException(403, "Public billing requires authenticated Xwav accounts")
        return identity

    def mutation_owner(request: Request) -> str:
        identity = owner(request)
        origin = request.headers.get("origin")
        expected = available().config.public_url.rstrip("/")
        public = urlsplit(expected)
        if origin and origin != f"{public.scheme}://{public.netloc}":
            raise HTTPException(403, "Cross-origin account mutation denied")
        if request.headers.get("sec-fetch-site") == "cross-site":
            raise HTTPException(403, "Cross-site account mutation denied")
        return identity

    @router.get("/billing")
    async def status(request: Request) -> dict[str, Any]:
        identity = owner(request)
        if service is None:
            return {
                "enabled": False,
                "message": (
                    "Set XWAV_BILLING_CONFIG and XWAV_BILLING_ENCRYPTION_KEY to enable"
                    " plans, provider models and BYOK."
                ),
            }
        return await asyncio.to_thread(service.status, identity)

    @router.put("/billing/selection")
    async def select(request: Request, body: Selection) -> dict[str, bool]:
        identity = mutation_owner(request)
        svc = available()
        _, model = svc.provider_model(body.model)
        svc.plan_period(identity, body.mode)
        if body.mode == "free" and not model.free:
            raise HTTPException(403, "Select a Free-plan model")
        await asyncio.to_thread(svc.store.update, identity, mode=body.mode, model=body.model)
        return {"saved": True}

    @router.put("/billing/keys/{provider}")
    async def save_key(provider: str, request: Request, body: KeyInput) -> dict[str, bool]:
        identity = mutation_owner(request)
        svc = available()
        if provider not in {p.id for p in svc.config.providers}:
            raise HTTPException(400, "Unknown provider")
        value = body.key.get_secret_value()
        if not value or len(value) > 8192 or any(c in value for c in "\r\n\x00"):
            raise HTTPException(400, "Invalid provider key")
        await asyncio.to_thread(svc.store.key, identity, provider, value)
        return {"saved": True}

    @router.delete("/billing/keys/{provider}")
    async def delete_key(provider: str, request: Request) -> dict[str, bool]:
        await asyncio.to_thread(available().store.key, mutation_owner(request), provider, "")
        return {"deleted": True}

    @router.post("/billing/token")
    async def token(request: Request) -> dict[str, str]:
        value = await asyncio.to_thread(available().store.rotate_token, mutation_owner(request))
        return {"token": value}

    @router.delete("/billing/token")
    async def revoke_token(request: Request) -> dict[str, bool]:
        await asyncio.to_thread(available().store.revoke_token, mutation_owner(request))
        return {"revoked": True}

    @router.post("/billing/members")
    async def invite(request: Request, body: MemberInput) -> dict[str, bool]:
        identity = mutation_owner(request)
        plan, _ = available().plan_period(identity, "managed")
        if not plan.per_seat or available().entitlement(identity).get("team_owner"):
            raise HTTPException(403, "Only the Teams subscription owner can allocate seats")
        await asyncio.to_thread(available().store.invite, identity, body.member)
        return {"invited": True}

    @router.post("/billing/members/accept")
    async def accept(request: Request) -> dict[str, bool]:
        await asyncio.to_thread(available().store.accept, mutation_owner(request))
        return {"accepted": True}

    @router.delete("/billing/members/{member}")
    async def remove_member(member: str, request: Request) -> dict[str, bool]:
        identity = mutation_owner(request)
        if member == "me":
            member = identity
        team = identity
        membership = available().store.membership(identity)
        if member == identity and membership:
            team = membership["team"]
        await asyncio.to_thread(available().store.remove_member, team, member)
        return {"removed": True}

    @router.post("/billing/checkout")
    async def checkout(request: Request, body: CheckoutInput) -> dict[str, str]:
        return await available().checkout(
            mutation_owner(request), body.plan, body.seats, body.annual
        )

    @router.post("/billing/portal")
    async def portal(request: Request) -> dict[str, str]:
        return await available().portal(mutation_owner(request))

    @router.post("/billing/webhook")
    async def webhook(request: Request) -> dict[str, bool]:
        await available().webhook(
            await bounded_body(request), request.headers.get("stripe-signature", "")
        )
        return {"received": True}

    @router.get("/billing/agent")
    async def agent(request: Request) -> Response:
        svc = available()
        account = await asyncio.to_thread(svc.store.account, owner(request))
        mode, model_id = account.get("mode", "free"), account.get("model", "")
        _, model = svc.provider_model(model_id)
        if model.protocol != "chat/completions":
            raise HTTPException(
                400, "Use the provider's native harness configuration for this protocol"
            )
        spec = {
            "spec_version": 1,
            "name": "Xwav subscription agent",
            "executor": {
                "type": "omnigent",
                "config": {"harness": "openai-agents", "use_responses": False},
                "model": model_id,
                "auth": {
                    "type": "api_key",
                    "api_key": "$XWAV_GATEWAY_TOKEN",
                    "base_url": svc.config.public_url.rstrip("/") + f"/v1/inference/{mode}",
                },
            },
            "tools": {"shell": {}, "file": {}},
        }
        output = io.BytesIO()
        content = json.dumps(spec, indent=2).encode()
        with tarfile.open(fileobj=output, mode="w:gz") as archive:
            info = tarfile.TarInfo("config.yaml")
            info.size = len(content)
            info.mode = 0o600
            archive.addfile(info, io.BytesIO(content))
        return Response(
            output.getvalue(),
            media_type="application/gzip",
            headers={
                "Content-Disposition": 'attachment; filename="xwav-subscription-agent.tar.gz"'
            },
        )

    @router.get("/inference/{mode}/models")
    async def models(mode: str, request: Request) -> dict[str, Any]:
        svc = available()
        identity, _ = await inference_owner(request, mode)
        if mode not in {"free", "managed", "byok"}:
            raise HTTPException(400, "Unknown usage mode")
        svc.plan_period(identity, mode)
        return {
            "object": "list",
            "data": [
                {"id": f"{p.id}/{m.id}", "object": "model", "owned_by": p.id}
                for p in svc.config.providers
                for m in p.models
                if mode != "free" or m.free
            ],
        }

    @router.post("/inference/{mode}/{protocol:path}")
    async def inference(mode: str, protocol: str, request: Request) -> Any:
        svc = available()
        identity, job = await inference_owner(request, mode)
        protocol = protocol.removeprefix("v1/")
        try:
            body = json.loads(await bounded_body(request))
        except ValueError:
            raise HTTPException(400, "Invalid model request JSON") from None
        if not isinstance(body, dict) or not isinstance(body.get("model"), str):
            raise HTTPException(400, "A provider/model identifier is required")
        tool_bridge = None
        if job:
            _, model = svc.provider_model(body["model"])
            for field in ("max_tokens", "max_completion_tokens", "max_output_tokens"):
                if type(body.get(field)) is int:
                    body[field] = min(body[field], model.max_output_tokens)
            if protocol == "responses" and isinstance(body.get("tools") or [], list):
                tool_bridge = ResponsesToolBridge(body)
                body = tool_bridge.request
        try:
            result = await svc.infer(identity, mode, protocol, body)
            return tool_bridge.wrap(result) if tool_bridge else result
        except HTTPException as error:
            if (
                request.headers.get("authorization", "").startswith("Bearer xwav_scan_")
                and error.status_code == 503
                and str(error.detail).startswith("All configured free models")
            ):
                # The gateway already exhausted its bounded free-pool retries.
                # Stop Strix's outer SDK from replaying that entire cycle five times.
                raise HTTPException(
                    424,
                    error.detail,
                    headers={**(error.headers or {}), "x-should-retry": "false"},
                ) from None
            raise

    return router

"""Bounded failover for configured, zero-cost free models; never replay delivered tools."""

from __future__ import annotations

import asyncio
import json
import math
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from fastapi import HTTPException
from starlette.responses import StreamingResponse

from omnigent.billing.config import BillingConfig, Model, Provider


class ProviderFailure(HTTPException):
    """An upstream failure, distinct from local authorization/usage denials."""


def _zero_cost(model: Model) -> bool:
    return model.free and model.input_usd_per_million == model.output_usd_per_million == 0


async def _completed_stream(response: StreamingResponse) -> StreamingResponse:
    chunks: list[bytes] = []
    size = 0
    pending = ""
    complete = False
    iterator = response.body_iterator
    try:
        async for chunk in iterator:
            raw = chunk.encode() if isinstance(chunk, str) else bytes(chunk)
            size += len(raw)
            if size > 2 * 1024 * 1024:
                raise ProviderFailure(502, "Free provider response exceeded the safe replay limit")
            chunks.append(raw)
            # The transport yields decoded text, preserving UTF-8 across network chunks.
            pending += raw.decode("utf-8")
            while "\n" in pending:
                line, pending = pending.split("\n", 1)
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    complete = True
                    continue
                try:
                    event = json.loads(data)
                except ValueError:
                    continue
                if not isinstance(event, dict):
                    continue
                if event.get("error") or event.get("type") in {
                    "error",
                    "response.failed",
                    "response.incomplete",
                }:
                    raise ProviderFailure(502, "Free provider response was interrupted")
                if event.get("type") in {"message_stop", "response.completed"}:
                    complete = True
        if not complete:
            raise ProviderFailure(502, "Free provider response ended before completion")
    except (httpx.HTTPError, UnicodeError, RuntimeError, TypeError, AttributeError) as error:
        raise ProviderFailure(502, "Free provider stream unavailable") from error
    finally:
        close = getattr(iterator, "aclose", None)
        if close is not None:
            await close()

    async def replay():
        for chunk in chunks:
            yield chunk

    return StreamingResponse(
        replay(), headers=dict(response.headers), media_type=response.media_type
    )


class FreeFailover:
    def __init__(self, config: BillingConfig):
        self.config = config
        self.cooldowns: dict[tuple[str, str, str], float] = {}

    def candidates(
        self, selected: tuple[Provider, Model], protocol: str
    ) -> list[tuple[Provider, Model]]:
        provider, model = selected
        rows = [
            (provider, entry) for entry in provider.models if entry.id in model.auto_candidates
        ]
        if rows:
            rows.sort(key=lambda row: model.auto_candidates.index(row[1].id))
        else:
            rows = [selected]
        rows += [
            (p, m)
            for p in self.config.providers
            for auto in p.models
            for candidate in auto.auto_candidates
            for m in p.models
            if m.id == candidate
        ]
        rows += [(p, m) for p in self.config.providers for m in p.models]
        result: list[tuple[Provider, Model]] = []
        seen: set[tuple[str, str]] = set()
        for candidate_provider, candidate in rows:
            key = (candidate_provider.id, candidate.id)
            if (
                key in seen
                or not _zero_cost(candidate)
                or candidate.auto_candidates
                or (
                    candidate.protocol != protocol
                    and protocol not in candidate_provider.compatible_protocols
                )
            ):
                continue
            seen.add(key)
            result.append((candidate_provider, candidate))
        return result

    def observe(
        self, provider: Provider, model: Model, protocol: str, headers: httpx.Headers
    ) -> None:
        """Avoid the next call when an upstream explicitly reports almost no headroom."""
        for name in (
            "x-ratelimit-remaining-requests",
            "x-ratelimit-remaining-tokens",
            "ratelimit-remaining",
        ):
            value = headers.get(name, "")
            if value.isdigit() and int(value) <= 1:
                raw_delay = headers.get("retry-after", headers.get("ratelimit-reset", "60"))
                delay = min(3600, max(1, int(raw_delay))) if raw_delay.isdigit() else 60
                key = (provider.id, model.id, protocol)
                self.cooldowns[key] = max(self.cooldowns.get(key, 0), time.monotonic() + delay)

    async def infer(
        self,
        selected: tuple[Provider, Model],
        protocol: str,
        body: dict[str, Any],
        invoke: Callable[[dict[str, Any], bool], Awaitable[Any]],
        credential_ready: Callable[[Provider], bool],
    ) -> Any:
        provider, model = selected
        if model.protocol != protocol and protocol not in provider.compatible_protocols:
            raise HTTPException(400, "This model requires a different harness API protocol")
        for field in ("max_tokens", "max_completion_tokens", "max_output_tokens"):
            if field in body and (
                type(body[field]) is not int or not 1 <= body[field] <= model.max_output_tokens
            ):
                raise HTTPException(
                    400, "Output token limit exceeds this model's configured maximum"
                )
        rows = [(p, m) for p, m in self.candidates(selected, protocol) if credential_ready(p)]
        now = time.monotonic()
        self.cooldowns = {key: until for key, until in self.cooldowns.items() if until > now}
        rows = [(p, m) for p, m in rows if (p.id, m.id, protocol) not in self.cooldowns]
        deadline = now + self.config.free_failover_timeout_seconds
        attempted = 0
        for provider, model in rows[: self.config.free_failover_max_attempts]:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            payload = {**body, "model": f"{provider.id}/{model.id}"}
            # Providers have different output limits; never exceed the next model's cap.
            for field in ("max_tokens", "max_completion_tokens", "max_output_tokens"):
                if type(payload.get(field)) is int:
                    payload[field] = min(payload[field], model.max_output_tokens)
            try:
                async with asyncio.timeout(
                    min(remaining, self.config.free_attempt_timeout_seconds)
                ):
                    result = await invoke(payload, attempted == 0)
                    if isinstance(result, StreamingResponse):
                        result = await _completed_stream(result)
                    elif not isinstance(result, dict) or result.get("error"):
                        raise ProviderFailure(502, "Free provider returned an invalid response")
                route = f"{provider.id}/{model.id}"
                if isinstance(result, StreamingResponse):
                    result.headers["X-Xwav-Model"] = route
                    result.headers["X-Xwav-Failovers"] = str(attempted)
                else:
                    result["xwav_routing"] = {"model": route, "failovers": attempted}
                return result
            except (ProviderFailure, TimeoutError) as error:
                delay = self.config.free_failover_cooldown_seconds
                if isinstance(error, ProviderFailure):
                    raw_delay = (error.headers or {}).get("Retry-After", "")
                    if raw_delay.isdigit():
                        delay = min(3600, max(1, int(raw_delay)))
                self.cooldowns[provider.id, model.id, protocol] = time.monotonic() + delay
                attempted += 1
        retry = min(
            (
                until - time.monotonic()
                for key, until in self.cooldowns.items()
                if key[2] == protocol
            ),
            default=self.config.free_failover_cooldown_seconds,
        )
        raise HTTPException(
            503,
            "All configured free models are temporarily unavailable. "
            "Retry after the indicated delay; no paid model was used.",
            headers={"Retry-After": str(max(1, math.ceil(retry)))},
        )

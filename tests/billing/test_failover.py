"""Safe free-pool failover across the real billing transport and quota ledger."""

import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException

from omnigent.billing.config import Model, Provider
from tests.billing.test_subscriptions import client as client
from tests.billing.test_subscriptions import service as service


@pytest.fixture
def free_service(service, monkeypatch):
    monkeypatch.setenv("SECOND_FREE_KEY", "second-test-secret")
    service.config.providers[0].models = [
        Model(id="auto", upstream="auto", free=True, auto_candidates=["first", "second"]),
        Model(id="first", upstream="first", free=True),
        Model(id="second", upstream="second", free=True),
        Model(id="paid", upstream="paid"),
    ]
    service.config.providers.append(
        Provider(
            id="other",
            label="Other free provider",
            base_url="https://other.test/v1",
            api_key_env="SECOND_FREE_KEY",
            models=[Model(id="third", upstream="third", free=True)],
        )
    )
    return service


def completion(text="healthy"):
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2},
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 402, 403, 404, 408, 429, 500, 502, 503])
async def test_free_falls_back_on_upstream_capacity_only_one_logical_request(free_service, status):
    calls = []

    def upstream(request):
        model = json.loads(request.content)["model"]
        calls.append(model)
        if model == "first":
            return httpx.Response(
                status, text="private-provider-secret", headers={"Retry-After": "17"}
            )
        return completion()

    free_service.transport = httpx.MockTransport(upstream)
    result = await free_service.infer("alice", "free", "chat/completions", {"model": "test/first"})
    assert calls == ["first", "second"]
    assert result["xwav_routing"] == {"model": "test/second", "failovers": 1}
    _, period = free_service.plan_period("alice", "free")
    assert free_service.store.usage("alice", period, "free")["requests"] == 1
    assert free_service.queue.active == 0
    calls.clear()
    await free_service.infer("bob", "free", "chat/completions", {"model": "test/first"})
    assert calls == ["second"]  # Global upstream cooldown; not another user's allowance.


@pytest.mark.asyncio
async def test_auto_pool_order_and_cross_provider_without_paid_models(free_service):
    calls = []

    def upstream(request):
        model = json.loads(request.content)["model"]
        calls.append(model)
        if model != "third":
            return httpx.Response(429)
        assert request.headers["authorization"] == "Bearer second-test-secret"
        return completion()

    free_service.transport = httpx.MockTransport(upstream)
    result = await free_service.infer("alice", "free", "chat/completions", {"model": "test/auto"})
    assert calls == ["first", "second", "third"]
    assert result["xwav_routing"]["model"] == "other/third"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["error", "eof", "socket"])
@pytest.mark.parametrize("protocol", ["chat/completions", "messages", "responses"])
async def test_interrupted_stream_replays_only_completed_fallback(free_service, failure, protocol):
    for provider in free_service.config.providers:
        provider.compatible_protocols = ["chat/completions", "messages", "responses"]
    calls = []
    done = {
        "chat/completions": "[DONE]",
        "messages": '{"type":"message_stop"}',
        "responses": '{"type":"response.completed"}',
    }[protocol]

    class BrokenStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"choices":[{"delta":{"tool_calls":[{"id":"unsafe-partial"}]}}]}\n\n'
            if failure == "socket":
                raise httpx.ReadError("secret-socket-error")
            if failure == "error":
                yield b'data: {"error":{"message":"private-upstream-error"}}\n\ndata: [DONE]\n\n'

    def upstream(request):
        model = json.loads(request.content)["model"]
        calls.append(model)
        if model == "first":
            return httpx.Response(200, stream=BrokenStream())
        return httpx.Response(200, text=f'data: {{"text":"safe-final"}}\n\ndata: {done}\n\n')

    free_service.transport = httpx.MockTransport(upstream)
    response = await free_service.infer(
        "alice", "free", protocol, {"model": "test/first", "stream": True}
    )
    text = "".join(
        [
            chunk.decode() if isinstance(chunk, bytes) else chunk
            async for chunk in response.body_iterator
        ]
    )
    assert calls == ["first", "second"]
    assert "safe-final" in text and "unsafe-partial" not in text and "private" not in text
    assert response.headers["X-Xwav-Model"] == "test/second"
    assert free_service.queue.active == 0


@pytest.mark.asyncio
async def test_near_quota_header_skips_model_on_next_request(free_service):
    calls = []

    def upstream(request):
        model = json.loads(request.content)["model"]
        calls.append(model)
        result = completion()
        result.headers["x-ratelimit-remaining-requests"] = "1"
        result.headers["Retry-After"] = "30"
        return result

    free_service.transport = httpx.MockTransport(upstream)
    for _ in range(2):
        await free_service.infer("alice", "free", "chat/completions", {"model": "test/first"})
    assert calls == ["first", "second"]


@pytest.mark.asyncio
async def test_exhaustion_is_bounded_retryable_redacted_and_never_paid(free_service):
    calls = []
    free_service.config.free_failover_max_attempts = 2

    def upstream(request):
        calls.append(json.loads(request.content)["model"])
        return httpx.Response(429, text="private-key", headers={"Retry-After": "17"})

    free_service.transport = httpx.MockTransport(upstream)
    with pytest.raises(HTTPException) as error:
        await free_service.infer("alice", "free", "chat/completions", {"model": "test/first"})
    assert calls == ["first", "second"]
    assert error.value.status_code == 503
    assert 1 <= int(error.value.headers["Retry-After"]) <= 17
    assert "private" not in error.value.detail
    assert free_service.queue.active == 0


@pytest.mark.asyncio
async def test_local_quota_invalid_requests_and_cancellation_never_failover(free_service):
    calls = []
    free_service.transport = httpx.MockTransport(
        lambda request: calls.append(request) or completion()
    )
    for index in range(10):
        await free_service.infer("alice", "free", "chat/completions", {"model": "test/first"})
    with pytest.raises(HTTPException) as error:
        await free_service.infer("alice", "free", "chat/completions", {"model": "test/first"})
    assert error.value.status_code == 429 and len(calls) == 10
    with pytest.raises(HTTPException) as error:
        await free_service.infer(
            "bob", "free", "chat/completions", {"model": "test/first", "max_tokens": 999999}
        )
    assert error.value.status_code == 400 and len(calls) == 10

    async def cancel(request):
        raise asyncio.CancelledError

    free_service.transport = httpx.MockTransport(cancel)
    with pytest.raises(asyncio.CancelledError):
        await free_service.infer(
            "bob", "free", "chat/completions", {"model": "test/first", "stream": True}
        )
    assert free_service.queue.active == 0


@pytest.mark.asyncio
async def test_attempt_timeout_advances_without_double_charging(free_service):
    free_service.config.free_attempt_timeout_seconds = 1
    calls = []

    async def upstream(request):
        model = json.loads(request.content)["model"]
        calls.append(model)
        if model == "first":
            await asyncio.sleep(5)
        return completion()

    free_service.transport = httpx.MockTransport(upstream)
    result = await free_service.infer("alice", "free", "chat/completions", {"model": "test/first"})
    assert calls == ["first", "second"] and result["xwav_routing"]["failovers"] == 1
    _, period = free_service.plan_period("alice", "free")
    assert free_service.store.usage("alice", period, "free")["requests"] == 1
    assert free_service.queue.active == 0


def test_completed_fallback_stream_through_real_http_route(free_service, client):
    calls = []

    def upstream(request):
        model = json.loads(request.content)["model"]
        calls.append(model)
        if model == "first":
            return httpx.Response(
                200, text='data: {"error":{"message":"secret interrupted"}}\n\ndata: [DONE]\n\n'
            )
        return httpx.Response(
            200, text='data: {"choices":[{"delta":{"content":"recovered"}}]}\n\ndata: [DONE]\n\n'
        )

    free_service.transport = httpx.MockTransport(upstream)
    token = free_service.store.rotate_token("alice")
    result = client.post(
        "/v1/inference/free/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"model": "test/first", "stream": True},
    )
    assert result.status_code == 200 and "recovered" in result.text and "secret" not in result.text
    assert result.headers["X-Xwav-Failovers"] == "1"
    assert calls == ["first", "second"]


@pytest.mark.asyncio
async def test_fallback_keeps_token_budget_even_when_request_is_reused(free_service):
    free_service.config.plans[0].token_limit = 5000
    calls = []

    async def upstream(request):
        calls.append(json.loads(request.content)["model"])
        raise httpx.ReadError("Unknown upstream outcome")

    free_service.transport = httpx.MockTransport(upstream)
    with pytest.raises(HTTPException) as error:
        await free_service.infer("alice", "free", "chat/completions", {"model": "test/first"})
    assert error.value.status_code == 429
    assert calls == ["first"]  # The next reservation cannot fit the remaining token allowance.
    _, period = free_service.plan_period("alice", "free")
    assert free_service.store.usage("alice", period, "free")["requests"] == 1


@pytest.mark.asyncio
async def test_subscriber_can_recover_free_models_without_entering_paid_pool(free_service):
    from tests.billing.test_subscriptions import active

    active(free_service)
    calls = []

    def upstream(request):
        model = json.loads(request.content)["model"]
        calls.append(model)
        return httpx.Response(429) if model == "first" else completion()

    free_service.transport = httpx.MockTransport(upstream)
    result = await free_service.infer(
        "alice", "managed", "chat/completions", {"model": "test/first"}
    )
    assert calls == ["first", "second"] and result["xwav_routing"]["model"] == "test/second"
    _, period = free_service.plan_period("alice", "managed")
    assert free_service.store.usage("alice", period, "managed")["requests"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 413, 422])
async def test_provider_validation_errors_are_not_retried_as_server_failures(free_service, status):
    calls = []
    free_service.transport = httpx.MockTransport(
        lambda request: (
            calls.append(request) or httpx.Response(status, text="private upstream detail")
        )
    )
    with pytest.raises(HTTPException) as error:
        await free_service.infer("alice", "free", "chat/completions", {"model": "test/auto"})
    assert error.value.status_code == status
    assert len(calls) == 1
    assert "private upstream detail" not in str(error.value.detail)


@pytest.mark.asyncio
async def test_provider_compatibility_omits_only_parallel_tool_hint(free_service):
    calls = []
    free_service.config.providers[0].omit_parallel_tool_calls = True
    free_service.transport = httpx.MockTransport(
        lambda request: calls.append(json.loads(request.content)) or completion()
    )
    await free_service.infer(
        "alice",
        "free",
        "chat/completions",
        {
            "model": "test/first",
            "parallel_tool_calls": False,
            "tool_choice": "required",
            "tools": [
                {
                    "type": "function",
                    "function": {"name": "inspect", "parameters": {"type": "object"}},
                }
            ],
        },
    )
    assert "parallel_tool_calls" not in calls[0]
    assert calls[0]["tool_choice"] == "required"
    assert calls[0]["tools"][0]["function"]["name"] == "inspect"

"""Real gateway HTTP contracts and atomic quota enforcement with scripted upstreams."""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from urllib.parse import parse_qs

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from omnigent.billing.config import BillingConfig
from omnigent.billing.service import BillingService
from omnigent.billing.store import BillingStore
from omnigent.errors import OmnigentError
from omnigent.server.routes.billing import create_billing_router
from omnigent.spec.parser import parse


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv("MANAGED_TEST_KEY", "operator-secret")
    monkeypatch.setenv("XWAV_STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setenv("PRICE_PRO", "price_pro")
    monkeypatch.setenv("PRICE_ANNUAL", "price_annual")
    monkeypatch.setenv("XWAV_STRIPE_WEBHOOK_SECRET", "whsec_fake")
    config = BillingConfig.model_validate(
        {
            "public_url": "https://xwav.test",
            "database": str(tmp_path / "billing.sqlite"),
            "plans": [
                {
                    "id": "free",
                    "label": "Free",
                    "monthly_usd": 0,
                    "included_micro_usd": 100000,
                    "request_limit": 10,
                },
                {
                    "id": "pro",
                    "label": "Pro",
                    "monthly_usd": 25,
                    "included_micro_usd": 0,
                    "token_limit": 10000000,
                    "rollover": True,
                    "stripe_price_env": "PRICE_PRO",
                    "annual_stripe_price_env": "PRICE_ANNUAL",
                    "annual_monthly_usd": 18,
                },
                {
                    "id": "teams",
                    "label": "Teams",
                    "monthly_usd": 30,
                    "included_micro_usd": 0,
                    "token_limit": 10000000,
                    "per_seat": True,
                },
            ],
            "providers": [
                {
                    "id": "test",
                    "label": "Test",
                    "base_url": "https://models.test/v1",
                    "api_key_env": "MANAGED_TEST_KEY",
                    "models": [
                        {
                            "id": "small",
                            "upstream": "actual-small",
                            "free": True,
                            "input_usd_per_million": 0.5,
                            "output_usd_per_million": 2,
                        },
                        {"id": "paid", "upstream": "actual-paid"},
                    ],
                }
            ],
        }
    )
    store = BillingStore(config.database, Fernet.generate_key().decode())
    svc = BillingService(config, store)
    yield svc
    store.engine.dispose()


class Identity:
    def get_user_id(self, request: Request):
        return request.headers.get("x-user")


@pytest.fixture
def client(service):
    app = FastAPI()
    app.include_router(create_billing_router(service, Identity()), prefix="/v1")
    with TestClient(app) as client:
        yield client


def active(service, owner="alice", **fields):
    service.store.update(
        owner,
        plan="pro",
        status="active",
        customer="cus_test",
        subscription="sub_test",
        period_start=int(time.time()) - 60,
        period_end=int(time.time()) + 86400,
        **fields,
    )


def test_scoped_keys_tokens_csrf_and_redaction(service, client):
    with pytest.raises(OmnigentError):
        client.get("/v1/billing")
    headers = {"x-user": "alice"}
    assert (
        client.put(
            "/v1/billing/keys/test",
            headers={**headers, "origin": "https://evil.test"},
            json={"key": "secret"},
        ).status_code
        == 403
    )
    assert (
        client.put(
            "/v1/billing/keys/test", headers=headers, json={"key": "private-key"}
        ).status_code
        == 200
    )
    assert service.store.key("alice", "test") == "private-key"
    assert service.store.key("bob", "test") is None
    assert b"private-key" not in __import__("pathlib").Path(service.config.database).read_bytes()
    assert "private-key" not in client.get("/v1/billing", headers=headers).text
    first = client.post("/v1/billing/token", headers=headers).json()["token"]
    second = client.post("/v1/billing/token", headers=headers).json()["token"]
    with pytest.raises(HTTPException):
        service.store.token_owner(first)
    assert service.store.token_owner(second) == "alice"
    client.delete("/v1/billing/token", headers=headers)
    with pytest.raises(HTTPException):
        service.store.token_owner(second)
    client.delete("/v1/billing/keys/test", headers=headers)
    assert service.store.key("alice", "test") is None


def test_atomic_reservation_under_contention(service):
    def attempt(_):
        try:
            service.store.reserve("alice", "cycle", "managed", 10, 100, 100, 10, 100)
            return True
        except HTTPException as error:
            assert error.status_code == 429
            return False

    with ThreadPoolExecutor(max_workers=16) as pool:
        assert sum(pool.map(attempt, range(64))) == 10
    assert service.store.usage("alice", "cycle", "managed") == {
        "spent_micro_usd": 100,
        "requests": 10,
        "tokens": 100,
    }
    service.store.settle("alice", "cycle", "managed", 10, 4, 10, 2)
    assert service.store.usage("alice", "cycle", "managed")["tokens"] == 92


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode,key",
    [("free", "operator-secret"), ("managed", "operator-secret"), ("byok", "own-secret")],
)
async def test_provider_routing_and_correct_usage_account(service, mode, key):
    active(service)
    service.store.key("alice", "test", "own-secret")

    def upstream(request):
        assert request.headers["authorization"] == f"Bearer {key}"
        assert json.loads(request.content)["model"] == "actual-small"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 4},
            },
        )

    service.transport = httpx.MockTransport(upstream)
    result = await service.infer(
        "alice",
        mode,
        "chat/completions",
        {"model": "test/small", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert result["choices"][0]["message"]["content"] == "ok"
    _, period = service.plan_period("alice", mode)
    usage = service.store.usage("alice", period, mode)
    assert usage["spent_micro_usd"] == (0 if mode == "byok" else 13)
    assert usage["tokens"] == (0 if mode == "byok" else 14)
    assert service.store.usage("bob", period, mode)["requests"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body,mode,status",
    [
        ({"model": "test/paid"}, "free", 403),
        ({"model": "test/small"}, "managed", 402),
        ({"model": "test/small", "max_tokens": 10000000}, "free", 400),
        ({"model": "test/small", "previous_response_id": "private"}, "free", 400),
    ],
)
async def test_denials_precede_network(service, body, mode, status):
    service.transport = httpx.MockTransport(
        lambda _: pytest.fail("Denied request reached provider")
    )
    with pytest.raises(HTTPException) as error:
        await service.infer("alice", mode, "chat/completions", body)
    assert error.value.status_code == status


def test_stream_through_real_route_and_settlement(service, client):
    events = (
        'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
        'data: {"choices":[],"usage":{"prompt_tokens":5,"completion_tokens":2}}\n\n'
        "data: [DONE]\n\n"
    )

    def upstream(request):
        assert json.loads(request.content)["stream_options"] == {"include_usage": True}
        return httpx.Response(200, text=events, headers={"content-type": "text/event-stream"})

    service.transport = httpx.MockTransport(upstream)
    token = service.store.rotate_token("alice")
    result = client.post(
        "/v1/inference/free/chat/completions",
        headers={"authorization": f"Bearer {token}"},
        json={"model": "test/small", "stream": True},
    )
    assert result.status_code == 200, result.text
    assert result.text == events
    _, period = service.plan_period("alice", "free")
    assert service.store.usage("alice", period, "free")["tokens"] == 7


@pytest.mark.asyncio
async def test_checkout_annual_seats_portal_and_webhook_truth(service, monkeypatch):
    calls = []
    subscription = {
        "id": "sub_test",
        "status": "active",
        "customer": "cus_test",
        "metadata": {"xwav_owner": "alice"},
        "items": {
            "data": [
                {
                    "price": {"id": "price_pro"},
                    "quantity": 1,
                    "current_period_start": int(time.time()) - 100,
                    "current_period_end": int(time.time()) + 86400,
                }
            ]
        },
    }

    def stripe(request):
        calls.append(request)
        if request.url.path.startswith("/v1/prices/"):
            annual = request.url.path.endswith("price_annual")
            return httpx.Response(
                200,
                json={
                    "currency": "usd",
                    "unit_amount": 21600 if annual else 2500,
                    "active": True,
                    "recurring": {"interval": "year" if annual else "month"},
                },
            )
        if request.method == "GET":
            return httpx.Response(200, json=subscription)
        return httpx.Response(200, json={"url": "https://checkout.stripe.com/test"})

    service.transport = httpx.MockTransport(stripe)
    await service.checkout("alice", "pro", annual=True)
    assert parse_qs(calls[-1].content.decode())["line_items[0][price]"] == ["price_annual"]
    assert calls[-1].headers.get("Idempotency-Key")
    event = {
        "id": "evt_test",
        "type": "customer.subscription.updated",
        "data": {"object": {"id": "sub_test"}},
    }

    def signed(data):
        raw = json.dumps(data).encode()
        stamp = str(int(time.time()))
        signature = hmac.new(
            b"whsec_fake", stamp.encode() + b"." + raw, hashlib.sha256
        ).hexdigest()
        return raw, f"t={stamp},v1={signature}"

    raw, signature = signed(event)
    with pytest.raises(HTTPException):
        await service.webhook(raw, signature + "tampered")
    await service.webhook(raw, signature)
    await service.webhook(raw, signature)
    assert service.plan_period("alice", "managed")[0].id == "pro"
    assert service.status("alice")["plan"] == "pro"
    await service.portal("alice")
    assert parse_qs(calls[-1].content.decode())["customer"] == ["cus_test"]
    with pytest.raises(HTTPException):
        await service.checkout("alice", "pro")
    subscription["status"] = "canceled"
    event["id"] = "evt_cancel"
    await service.webhook(*signed(event))
    with pytest.raises(HTTPException):
        service.plan_period("alice", "managed")


def test_team_allocations_require_acceptance_and_respect_seats(service):
    active(service, seats=2)
    service.store.update("alice", plan="teams")
    service.store.invite("alice", "bob")
    with pytest.raises(HTTPException):
        service.plan_period("bob", "managed")
    service.store.accept("bob")
    assert service.plan_period("bob", "managed")[0].id == "teams"
    with pytest.raises(HTTPException):
        service.store.invite("alice", "carol")
    service.store.update("alice", seats=1)
    with pytest.raises(HTTPException):
        service.plan_period("bob", "managed")
    service.store.remove_member("alice", "bob")
    assert service.store.membership("bob") is None


def test_monthly_allowance_rollover_and_annual_resets(service):
    from dateutil.relativedelta import relativedelta

    now = datetime.now(UTC)
    start = (now - relativedelta(months=3)).replace(day=1)
    active(service)
    service.store.update(
        "alice",
        period_start=int(start.timestamp()),
        period_end=int((start + relativedelta(years=1)).timestamp()),
        entitlement_start=int(start.timestamp()),
    )
    plan, period = service.plan_period("alice", "managed")
    previous = service.period(service.entitlement("alice"), -1)
    service.store.reserve("alice", previous, "managed", 0, None, 100, 2000000, 10000000)
    assert service.token_allowance("alice", "managed", plan) == 18000000
    assert str(now.year) in period


def test_downloaded_agent_is_parseable_and_has_no_keys(service, client, tmp_path, monkeypatch):
    service.store.update("alice", model="test/small", mode="free")
    response = client.get("/v1/billing/agent", headers={"x-user": "alice"})
    assert response.status_code == 200
    with tarfile.open(fileobj=io.BytesIO(response.content)) as archive:
        content = archive.extractfile("config.yaml").read()
    assert b"operator-secret" not in content
    assert b"$XWAV_GATEWAY_TOKEN" in content
    monkeypatch.setenv("XWAV_GATEWAY_TOKEN", "xwav_test")
    (tmp_path / "config.yaml").write_bytes(content)
    spec = parse(tmp_path)
    assert spec.executor.config["use_responses"] == "False"
    assert spec.executor.auth.base_url.endswith("/v1/inference/free")


@pytest.mark.asyncio
async def test_interrupted_or_unpriced_stream_keeps_reservation(service):
    # A socket ending before final usage must never appear as a free successful request.
    service.transport = httpx.MockTransport(
        lambda _: httpx.Response(200, text='data: {"choices":[]}\n\n')
    )
    response = await service.infer(
        "alice", "free", "chat/completions", {"model": "test/small", "stream": True}
    )
    async for _ in response.body_iterator:
        pass
    _, period = service.plan_period("alice", "free")
    assert service.store.usage("alice", period, "free")["tokens"] > 0
    assert service.queue.active == 0


@pytest.mark.asyncio
async def test_provider_rejection_redacts_body_and_releases_reservation(service):
    service.transport = httpx.MockTransport(lambda _: httpx.Response(401, text="operator-secret"))
    with pytest.raises(HTTPException) as error:
        await service.infer("alice", "free", "chat/completions", {"model": "test/small"})
    assert "operator-secret" not in str(error.value.detail)
    _, period = service.plan_period("alice", "free")
    assert service.store.usage("alice", period, "free")["tokens"] == 0
    assert service.queue.active == 0


@pytest.mark.asyncio
async def test_priority_queue_prefers_paid_requests_and_is_bounded():
    import asyncio

    from omnigent.billing.queue import InferenceQueue

    queue = InferenceQueue(capacity=1, max_waiting=2)
    order = []
    await queue.acquire(False)

    async def worker(name, paid):
        await queue.acquire(paid)
        order.append(name)
        await queue.release()

    free = asyncio.create_task(worker("free", False))
    paid = asyncio.create_task(worker("paid", True))
    await asyncio.sleep(0)
    with pytest.raises(HTTPException):
        await queue.acquire(True)
    await queue.release()
    await asyncio.gather(free, paid)
    assert order == ["paid", "free"]
    assert queue.active == queue.waiting == 0


@pytest.mark.parametrize(
    "url",
    ["ftp://example.com", "https://key:secret@example.com", "https://example.com?key=secret"],
)
def test_provider_endpoints_are_operator_only_validated(service, url):
    config = service.config.model_dump()
    config["providers"][0]["base_url"] = url
    with pytest.raises(ValueError):
        BillingConfig.model_validate(config)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extra",
    [
        {"tools": [{"type": "web_search"}]},
        {"messages": [{"content": [{"type": "image", "source": {"data": "unmetered"}}]}]},
        {"modalities": ["audio"]},
    ],
)
async def test_unpriced_managed_modalities_are_denied(service, extra):
    service.transport = httpx.MockTransport(
        lambda _: pytest.fail("Unmetered feature reached upstream")
    )
    with pytest.raises(HTTPException) as error:
        await service.infer("alice", "free", "chat/completions", {"model": "test/small", **extra})
    assert error.value.status_code == 400


def test_cli_initialization_is_private_idempotent_and_matches_user_prices(tmp_path):
    from click.testing import CliRunner

    from omnigent.cli_billing import billing

    result = CliRunner().invoke(billing, ["init", "--directory", str(tmp_path / "billing config")])
    assert result.exit_code == 0, result.output
    config = BillingConfig.model_validate_json(
        (tmp_path / "billing config/plans.json").read_text()
    )
    assert {p.id: p.monthly_usd for p in config.plans} == {
        "free": 0,
        "pro": 25,
        "teams": 30,
        "scale-1000": 200,
        "scale-2500": 500,
        "scale-5000": 900,
        "scale-10000": 1800,
    }
    assert config.plans[1].token_limit == 10000000
    assert config.plans[1].annual_monthly_usd == 18
    assert config.plans[2].annual_monthly_usd == 27
    assert config.plans[3].included_micro_usd == 50000000
    assert (tmp_path / "billing config/billing.env").stat().st_mode & 0o777 == 0o600
    assert "XWAV_BILLING_ENCRYPTION_KEY" not in result.output
    assert (
        CliRunner()
        .invoke(billing, ["init", "--directory", str(tmp_path / "billing config")])
        .exit_code
        != 0
    )


def test_gateway_model_catalog_is_plan_scoped(service, client):
    token = service.store.rotate_token("alice")
    result = client.get("/v1/inference/free/models", headers={"authorization": f"Bearer {token}"})
    assert result.status_code == 200
    assert [row["id"] for row in result.json()["data"]] == ["test/small"]
    assert (
        client.get(
            "/v1/inference/managed/models", headers={"authorization": f"Bearer {token}"}
        ).status_code
        == 402
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "protocol,usage",
    [
        ("messages", {"input_tokens": 3, "output_tokens": 2}),
        ("responses", {"input_tokens": 3, "output_tokens": 2}),
    ],
)
async def test_native_provider_protocol_passthrough(service, protocol, usage):
    service.config.providers[0].models[0].protocol = protocol

    def upstream(request):
        assert request.url.path == "/v1/" + protocol
        if protocol == "messages":
            assert request.headers["x-api-key"] == "operator-secret"
            assert request.headers["anthropic-version"] == "2023-06-01"
        return httpx.Response(200, json={"usage": usage, "id": "result"})

    service.transport = httpx.MockTransport(upstream)
    result = await service.infer("alice", "free", protocol, {"model": "test/small"})
    assert result["id"] == "result"


@pytest.mark.asyncio
async def test_real_agent_sdk_tool_roundtrip_uses_gateway_and_bills_correct_owner(service):
    from agents import Agent, OpenAIChatCompletionsModel, RunConfig, Runner, function_tool
    from openai import AsyncOpenAI

    calls = []

    @function_tool
    def read_project() -> str:
        """Read the disposable test project."""
        return "xwav-project-proof"

    def provider(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert payload["model"] == "actual-small"
        if len(calls) == 1:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_read",
                        "type": "function",
                        "function": {"name": "read_project", "arguments": "{}"},
                    }
                ],
            }
            reason = "tool_calls"
        else:
            assert any(
                m.get("role") == "tool" and "xwav-project-proof" in m["content"]
                for m in payload["messages"]
            )
            message = {"role": "assistant", "content": "Project verified."}
            reason = "stop"
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_test",
                "object": "chat.completion",
                "created": 1,
                "model": "actual-small",
                "choices": [{"index": 0, "message": message, "finish_reason": reason}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
            },
        )

    service.transport = httpx.MockTransport(provider)
    token = service.store.rotate_token("alice")
    app = FastAPI()
    app.include_router(create_billing_router(service), prefix="/v1")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as http:
        client = AsyncOpenAI(
            api_key=token, base_url="https://xwav.test/v1/inference/free", http_client=http
        )
        agent = Agent(
            name="Gateway test",
            model=OpenAIChatCompletionsModel(model="test/small", openai_client=client),
            tools=[read_project],
        )
        result = await Runner.run(
            agent, "Read the project and verify it.", run_config=RunConfig(tracing_disabled=True)
        )
        assert result.final_output == "Project verified."
    _, period = service.plan_period("alice", "free")
    assert service.store.usage("alice", period, "free")["tokens"] == 28
    assert service.store.usage("alice", period, "free")["requests"] == 2


@pytest.mark.asyncio
async def test_checkout_cannot_charge_a_price_that_differs_from_display(service):
    calls = []

    def stripe(request):
        calls.append(request.method)
        return httpx.Response(
            200,
            json={
                "currency": "usd",
                "unit_amount": 250000,
                "active": True,
                "recurring": {"interval": "month"},
            },
        )

    service.transport = httpx.MockTransport(stripe)
    with pytest.raises(HTTPException) as error:
        await service.checkout("alice", "pro")
    assert error.value.status_code == 503
    assert calls == ["GET"]


def test_public_billing_cannot_use_anonymous_local_account(service):
    app = FastAPI()
    app.include_router(create_billing_router(service), prefix="/v1")
    with TestClient(app) as client:
        assert client.get("/v1/billing").status_code == 403
        assert client.post("/v1/billing/token").status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "configured,client_field,expected",
    [
        (None, "max_completion_tokens", "max_completion_tokens"),
        ("max_completion_tokens", "max_tokens", "max_completion_tokens"),
        (None, "max_tokens", "max_tokens"),
    ],
)
async def test_new_model_output_token_parameter_needs_only_registry_configuration(
    service, configured, client_field, expected
):
    service.config.providers[0].models[0].output_token_field = configured

    def upstream(request):
        payload = json.loads(request.content)
        assert payload[expected] == 100
        assert (
            sum(
                field in payload
                for field in ("max_tokens", "max_completion_tokens", "max_output_tokens")
            )
            == 1
        )
        return httpx.Response(200, json={"usage": {"prompt_tokens": 1, "completion_tokens": 1}})

    service.transport = httpx.MockTransport(upstream)
    await service.infer(
        "alice", "free", "chat/completions", {"model": "test/small", client_field: 100}
    )

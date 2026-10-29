"""FreeLLMAPI connector keeps credentials private and imports approved usable IDs only."""

from __future__ import annotations

import httpx
import pytest

from omnigent.billing.config import BillingConfig
from omnigent.billing.freellmapi import connect_freellmapi
from tests.billing.test_subscriptions import service as service


def test_connects_only_selected_models_and_preserves_other_plans(service, tmp_path):
    config = tmp_path / "plans.json"
    config.write_text(service.config.model_dump_json())
    key = tmp_path / "unified.key"
    key.write_text("gateway-test-secret\n")
    env = tmp_path / "billing.env"
    env.write_text("XWAV_BILLING_ENCRYPTION_KEY=keep-existing-key\n")

    def catalog(request):
        assert request.headers["authorization"] == "Bearer gateway-test-secret"
        assert request.url.params["available"] == "true"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "auto"},
                    {"id": "llama", "available": True},
                    {"id": "unconnected", "available": False},
                    {"id": "fusion"},
                ]
            },
        )

    selected = connect_freellmapi(
        config,
        "http://127.0.0.1:4000/v1",
        key,
        ("auto", "llama", "auto"),
        transport=httpx.MockTransport(catalog),
    )
    assert selected == ["auto", "llama"]
    saved = BillingConfig.model_validate_json(config.read_text())
    assert saved.plans == service.config.plans
    assert saved.providers[0] == service.config.providers[0]
    provider = saved.providers[-1]
    assert provider.label == "FreeLLMAPI"
    assert [m.id for m in provider.models] == ["auto", "llama"]
    assert all(
        m.free and m.input_usd_per_million == m.output_usd_per_million == 0
        for m in provider.models
    )
    assert "gateway-test-secret" not in config.read_text()
    assert "keep-existing-key" in env.read_text()
    assert env.stat().st_mode & 0o777 == config.stat().st_mode & 0o777 == 0o600
    # Reconfiguration replaces rather than duplicates the provider/key reference.
    connect_freellmapi(
        config, "http://127.0.0.1:4000/v1", key, ("llama",), transport=httpx.MockTransport(catalog)
    )
    assert env.read_text().count("XWAV_FREE_GATEWAY_KEY=") == 1
    assert len(BillingConfig.model_validate_json(config.read_text()).providers) == 2


@pytest.mark.parametrize(
    "status,rows",
    [
        (401, []),
        (302, []),
        (200, [{"id": "unconnected", "available": False}]),
        (200, [{"id": "other"}]),
    ],
)
def test_failed_discovery_never_changes_active_configuration(service, tmp_path, status, rows):
    config = tmp_path / "plans.json"
    original = service.config.model_dump_json()
    config.write_text(original)
    key = tmp_path / "unified.key"
    key.write_text("gateway-test-secret")
    with pytest.raises(ValueError):
        connect_freellmapi(
            config,
            "http://127.0.0.1:4000/v1",
            key,
            ("unconnected",),
            transport=httpx.MockTransport(lambda _: httpx.Response(status, json={"data": rows})),
        )
    assert config.read_text() == original
    assert not (tmp_path / "billing.env").exists()


def test_an_auto_alias_alone_is_not_evidence_of_a_working_free_backend(service, tmp_path):
    config = tmp_path / "plans.json"
    config.write_text(service.config.model_dump_json())
    key = tmp_path / "unified.key"
    key.write_text("gateway-test-secret")
    with pytest.raises(ValueError, match="concrete"):
        connect_freellmapi(
            config,
            "http://127.0.0.1:4000/v1",
            key,
            ("auto",),
            transport=httpx.MockTransport(lambda _: pytest.fail("No discovery should run")),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,retry,expected",
    [(429, "17", "17"), (503, "99999", "3600"), (429, "private-key", "60")],
)
@pytest.mark.parametrize("stream", [False, True])
async def test_gateway_capacity_errors_keep_retry_headers_private_and_bounded(
    service, status, retry, expected, stream
):
    from fastapi import HTTPException

    service.transport = httpx.MockTransport(
        lambda _: httpx.Response(
            status, headers={"Retry-After": retry}, text="private-provider-key"
        )
    )
    with pytest.raises(HTTPException) as error:
        await service.infer(
            "alice", "free", "chat/completions", {"model": "test/small", "stream": stream}
        )
    assert error.value.status_code == status
    assert error.value.headers == {"Retry-After": expected}
    assert "private" not in str(error.value.detail)
    assert service.queue.active == 0


def test_auto_pool_requires_explicit_registered_concrete_models(service, tmp_path):
    config = tmp_path / "plans.json"
    config.write_text(service.config.model_dump_json())
    key = tmp_path / "key"
    key.write_text("test-key")
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200, json={"data": [{"id": "auto"}, {"id": "fast"}, {"id": "large"}]}
        )
    )
    connect_freellmapi(
        config,
        "http://localhost:4000/v1",
        key,
        ("auto", "fast", "large"),
        auto_model_ids=("large", "fast", "large"),
        transport=transport,
    )
    saved = BillingConfig.model_validate_json(config.read_text())
    assert saved.providers[-1].models[0].auto_candidates == ["large", "fast"]
    original = config.read_text()
    for pool in [("missing",), ("auto",), ("fusion",)]:
        with pytest.raises(ValueError, match="Auto candidates"):
            connect_freellmapi(
                config,
                "http://localhost:4000/v1",
                key,
                ("auto", "fast"),
                auto_model_ids=pool,
                transport=transport,
            )
        assert config.read_text() == original


@pytest.mark.parametrize("candidates", [["missing"], ["auto"], ["fast", "fast"]])
def test_registry_rejects_invalid_auto_candidates(service, candidates):
    from omnigent.billing.config import Model, Provider

    with pytest.raises(ValueError, match="Auto candidates"):
        Provider(
            id="test",
            label="Test",
            base_url="http://localhost:4000/v1",
            models=[
                Model(id="auto", upstream="auto", auto_candidates=candidates),
                Model(id="fast", upstream="fast"),
            ],
        )

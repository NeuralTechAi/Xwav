"""Automatic Free job bindings, credential isolation and startup probes."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from fastapi import HTTPException

from omnigent.billing.jobs import (
    GATEWAY_JOB_HARNESSES,
    JOB_PROVIDER,
    gateway_job_snapshot,
    install_job_token,
    job_identity,
)
from omnigent.inference_config import parse_inference_config, resolve_bound_provider
from tests.billing.test_subscriptions import client as client
from tests.billing.test_subscriptions import service as service


@pytest.mark.parametrize("harness", sorted(GATEWAY_JOB_HARNESSES))
def test_free_jobs_bind_without_vendor_keys(service, harness):
    service.config.providers[0].compatible_protocols = [
        "chat/completions",
        "responses",
        "messages",
    ]
    snapshot = gateway_job_snapshot(service, SimpleNamespace(provider="docker"), harness, "alice")
    assert snapshot["owner_id"] == "alice"
    runtime = snapshot["runtime_config"]
    assert parse_inference_config(runtime)[harness].default_model == "test/small"
    assert resolve_bound_provider(runtime, harness).name == JOB_PROVIDER
    assert "operator-secret" not in json.dumps(snapshot)
    assert "xwav_job_" not in json.dumps(snapshot)
    assert snapshot["catalog"]["status"] == "ready"


def test_explicit_credentials_are_preserved(service):
    target = SimpleNamespace(provider="docker")
    assert gateway_job_snapshot(service, target, "pi-native", "alice", auth=object()) is None
    service.store.update("alice", mode="byok")
    assert gateway_job_snapshot(service, target, "pi-native", "alice") is None
    with pytest.raises(ValueError, match="own account"):
        gateway_job_snapshot(service, target, "cursor-native", "bob")


def job_token(service):
    return (
        "xwav_job_"
        + service.store.cipher.encrypt(
            json.dumps({"host": "host", "launch": "host-secret", "scope": "free"}).encode()
        ).decode()
    )


def test_private_token_revocation_and_free_scope(service, monkeypatch):
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("XWAV_BILLING_ENCRYPTION_KEY", key)
    service.store.cipher = Fernet(key.encode())
    launcher = Mock()
    launcher.run.return_value.returncode = 0
    install_job_token(
        launcher, "sandbox", "host", "host-secret", {"providers": {JOB_PROVIDER: {}}}
    )
    command = launcher.run.call_args.args[1]
    assert "host-secret" not in command and "0o600" in command
    token = job_token(service)
    hosts = Mock()
    hosts.resolve_launch_token.return_value = SimpleNamespace(
        user_id="alice", sandbox_provider="docker"
    )
    assert job_identity(service, hosts, token, "free") == "alice"
    hosts.resolve_launch_token.assert_called_once_with("host", "host-secret")
    with pytest.raises(HTTPException):
        job_identity(service, hosts, token, "managed")
    hosts.resolve_launch_token.return_value = None
    with pytest.raises(HTTPException):
        job_identity(service, hosts, token, "free")
    with pytest.raises(HTTPException):
        job_identity(service, hosts, token + "bad", "free")


def test_install_failure_redacts_provider_error(monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("XWAV_BILLING_ENCRYPTION_KEY", Fernet.generate_key().decode())
    launcher = Mock()
    launcher.run.side_effect = RuntimeError("provider echoed sensitive arguments")
    with pytest.raises(RuntimeError, match=r"^Cannot install the job inference credential$"):
        install_job_token(launcher, "sandbox", "host", "secret", {"providers": {JOB_PROVIDER: {}}})


def test_startup_only_probes_selected_harness(monkeypatch):
    from omnigent.onboarding import harness_install
    from omnigent.onboarding import harness_readiness as readiness

    config = {
        "providers": {JOB_PROVIDER: {}},
        "inference": {"harnesses": {"pi-native": {"provider": JOB_PROVIDER}}},
    }
    monkeypatch.setattr(readiness, "load_config", lambda: config)
    probe = Mock(return_value=None)
    monkeypatch.setattr(harness_install, "missing_harness_cli", probe)
    monkeypatch.setattr(
        readiness, "_cli_family_availability", lambda *a: pytest.fail("Unrelated login probe")
    )
    assert readiness.configured_harness_map()["pi-native"] is True
    probe.assert_called_once_with("pi-native")


@pytest.mark.parametrize("protocol", ["chat/completions", "responses", "v1/messages"])
def test_job_routes_and_native_output_limits(service, client, protocol):
    service.config.providers[0].compatible_protocols = [
        "chat/completions",
        "responses",
        "messages",
    ]
    hosts = Mock()
    hosts.resolve_launch_token.return_value = SimpleNamespace(
        user_id="alice", sandbox_provider="docker"
    )
    client.app.state.host_store = hosts
    token = job_token(service)
    seen = []

    def upstream(request):
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1},
            },
        )

    service.transport = httpx.MockTransport(upstream)
    result = client.post(
        "/v1/inference/free/" + protocol,
        headers={"x-api-key": token},
        json={
            "model": "test/small",
            "max_tokens": 100000,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert result.status_code == 200, result.text
    assert (
        seen[0].get("max_tokens", seen[0].get("max_output_tokens"))
        == service.config.providers[0].models[0].max_output_tokens
    )
    assert (
        client.get(
            "/v1/inference/managed/models", headers={"Authorization": "Bearer " + token}
        ).status_code
        == 401
    )


def test_function_schema_source_field_is_not_a_media_attachment(service, client):
    service.transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200,
            json={
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                "choices": [{"message": {"content": "ok"}}],
            },
        )
    )
    token = service.store.rotate_token("alice")
    result = client.post(
        "/v1/inference/free/chat/completions",
        headers={"Authorization": "Bearer " + token},
        json={
            "model": "test/small",
            "messages": [{"role": "user", "content": "edit source"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "edit",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "source": {"type": "string"},
                                "image": {"type": "string"},
                            },
                        },
                    },
                }
            ],
        },
    )
    assert result.status_code == 200, result.text


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("deferred", [False, True])
def test_job_custom_patch_roundtrip(service, client, stream, deferred):
    service.config.providers[0].compatible_protocols = ["responses"]
    hosts = Mock()
    hosts.resolve_launch_token.return_value = SimpleNamespace(
        user_id="alice", sandbox_provider="docker"
    )
    client.app.state.host_store = hosts
    token = job_token(service)
    patch = "*** Begin Patch\n*** Add File: hello.txt\n+Hello 世界\n*** End Patch"
    raw_input = f"text(await tools.apply_patch({json.dumps(patch)}));" if deferred else patch
    tool_name = "functions__exec" if deferred else "apply_patch"
    call = {
        "type": "function_call",
        "id": "fc_patch",
        "call_id": "call_patch",
        "name": tool_name,
        "arguments": json.dumps({"input": raw_input}),
    }
    response = {
        "id": "resp_patch",
        "object": "response",
        "status": "completed",
        "output": [call],
        "usage": {"input_tokens": 2, "output_tokens": 1},
    }
    seen = []

    def upstream(request):
        body = json.loads(request.content)
        seen.append(body)
        tool = body["tools"][0]
        assert tool["name"] == tool_name
        assert tool["type"] == "function"
        assert tool["parameters"]["required"] == ["input"]
        if not stream:
            return httpx.Response(200, json=response)
        events = [
            {
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {**call, "arguments": ""},
            },
            {
                "type": "response.function_call_arguments.delta",
                "item_id": "fc_patch",
                "output_index": 0,
                "delta": call["arguments"],
            },
            {
                "type": "response.function_call_arguments.done",
                "item_id": "fc_patch",
                "output_index": 0,
                "arguments": call["arguments"],
            },
            {"type": "response.output_item.done", "output_index": 0, "item": call},
            {"type": "response.completed", "response": response},
        ]
        content = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)
        return httpx.Response(200, content=content, headers={"content-type": "text/event-stream"})

    service.transport = httpx.MockTransport(upstream)
    body = {
        "model": "test/small",
        "stream": stream,
        "input": [{"role": "user", "content": "Create hello.txt"}],
        "tools": [
            {
                "type": "custom",
                "name": "apply_patch",
                "description": "Apply a patch",
                "format": {"type": "text"},
            },
            {"type": "web_search"},
        ],
    }
    if deferred:
        body["input"].insert(
            0,
            {
                "type": "additional_tools",
                "tools": [
                    {
                        "type": "namespace",
                        "name": "functions",
                        "tools": [
                            {"type": "custom", "name": "exec", "description": "Run JavaScript"}
                        ],
                    }
                ],
            },
        )
        body["tools"] = []
    headers = {"Authorization": "Bearer " + token}
    result = client.post("/v1/inference/free/responses", headers=headers, json=body)
    assert result.status_code == 200, result.text
    if stream:
        events = [
            json.loads(line[6:]) for line in result.text.splitlines() if line.startswith("data: ")
        ]
        delta = next(e for e in events if e["type"] == "response.custom_tool_call_input.delta")
        assert delta["delta"] == raw_input
        assert not any(e["type"].startswith("response.function_call_arguments") for e in events)
        assert [e["sequence_number"] for e in events] == list(range(len(events)))
        restored = events[-1]["response"]["output"][0]
    else:
        restored = result.json()["output"][0]
    expected = {
        k: v
        for k, v in {**call, "type": "custom_tool_call", "input": raw_input}.items()
        if k != "arguments"
    }
    if deferred:
        expected.update(name="exec", namespace="functions")
    assert restored == expected
    body["input"] += [
        restored,
        {"type": "custom_tool_call_output", "call_id": "call_patch", "output": "Success"},
    ]
    retry = client.post("/v1/inference/free/responses", headers=headers, json=body)
    assert retry.status_code == 200, retry.text
    assert seen[-1]["input"][1]["type"] == "function_call"
    assert seen[-1]["input"][1]["name"] == tool_name
    assert json.loads(seen[-1]["input"][1]["arguments"]) == {"input": raw_input}
    assert seen[-1]["input"][2]["type"] == "function_call_output"


def test_subscription_jobs_use_selected_paid_profile(service):
    from tests.billing.test_subscriptions import active

    active(service, "alice", mode="managed", model="test/paid")
    snapshot = gateway_job_snapshot(
        service, SimpleNamespace(provider="docker"), "openai-agents", "alice"
    )
    binding = parse_inference_config(snapshot["runtime_config"])["openai-agents"]
    assert binding.default_model == "test/paid"
    family = snapshot["runtime_config"]["providers"][JOB_PROVIDER]["openai"]
    assert family["base_url"].endswith("/v1/inference/managed")
    assert "operator-secret" not in json.dumps(snapshot)
    service.store.update("alice", status="canceled")
    with pytest.raises(HTTPException):
        gateway_job_snapshot(service, SimpleNamespace(provider="docker"), "openai-agents", "alice")


def test_job_token_cannot_switch_usage_modes(service):
    hosts = Mock()
    hosts.resolve_launch_token.return_value = SimpleNamespace(
        user_id="alice", sandbox_provider="docker"
    )
    token = (
        "xwav_job_"
        + service.store.cipher.encrypt(
            json.dumps({"host": "h", "launch": "t", "scope": "managed"}).encode()
        ).decode()
    )
    assert job_identity(service, hosts, token, "managed") == "alice"
    with pytest.raises(HTTPException):
        job_identity(service, hosts, token, "free")
    with pytest.raises(HTTPException):
        job_identity(service, hosts, token, "byok")


def test_free_models_do_not_pretend_to_support_other_protocols(service):
    with pytest.raises(ValueError, match="No configured model endpoint"):
        gateway_job_snapshot(service, SimpleNamespace(provider="docker"), "claude-native", "alice")


def test_shipped_free_allowance_is_one_thousand_requests():
    from importlib.resources import files

    plans = json.loads(files("omnigent.billing").joinpath("plans.json").read_text())["plans"]
    assert next(p for p in plans if p["id"] == "free")["request_limit"] == 1000


def test_native_openai_client_receives_job_credentials_only(service, monkeypatch, tmp_path):
    from pathlib import Path

    from omnigent.billing.jobs import gateway_terminal_environment
    from omnigent.inference_config import inference_config_scope

    snapshot = gateway_job_snapshot(
        service, SimpleNamespace(provider="docker"), "qwen-native", "alice"
    )
    directory = tmp_path / ".omnigent"
    directory.mkdir()
    (directory / "xwav-job-token").write_text("xwav_job_test")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    with inference_config_scope(snapshot["runtime_config"]):
        env = gateway_terminal_environment("qwen-native")
    assert env["OPENAI_API_KEY"] == "xwav_job_test"
    assert env["OPENAI_BASE_URL"].endswith("/v1/inference/free")
    assert env["OPENAI_MODEL"] == "test/small"
    assert "operator-secret" not in json.dumps(env)

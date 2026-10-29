"""Automatic plan-based inference for isolated jobs, without vendor credentials."""

from __future__ import annotations

import base64
import json
import os
import shlex
from typing import Any

from omnigent.inference_config import inference_revision, normalize_inference_harness

JOB_PROVIDER = "xwav-job"
JOB_AUTH_COMMAND = 'cat "$HOME/.omnigent/xwav-job-token"'
# These adapters already honor authoritative provider bindings.
GATEWAY_JOB_HARNESSES = frozenset(
    {
        "pi",
        "pi-native",
        "codex",
        "codex-native",
        "claude-sdk",
        "claude-native",
        "openai-agents",
        "qwen",
        "qwen-native",
        "opencode-native",
        "jcode",
    }
)


def gateway_job_snapshot(
    service: Any, target: Any, harness: str, owner: str, auth: object = None
) -> dict[str, Any] | None:
    """Use the account gateway only when no agent/operator provider was selected."""
    # Entrypoint-based remote providers need their own secret-volume bootstrap.
    if target.provider != "docker":
        return None
    if (
        service is None
        or auth is not None
        or service.store.account(owner).get("mode", "free") == "byok"
    ):
        return None
    mode = service.store.account(owner).get("mode", "free")
    service.plan_period(owner, mode)
    harness = normalize_inference_harness(harness)
    if harness not in GATEWAY_JOB_HARNESSES:
        raise ValueError(
            f"{harness} cannot use the automatic Xwav gateway. "
            "Choose Pi, OpenAI Agents, Claude, Codex, Qwen or OpenCode; "
            "vendor-only harnesses require their own account."
        )
    protocol = (
        "messages"
        if harness in {"claude-sdk", "claude-native"}
        else "responses"
        if harness in {"codex", "codex-native"}
        else "chat/completions"
    )
    models = [
        f"{p.id}/{m.id}"
        for p in service.config.providers
        if os.getenv(p.api_key_env)
        for m in p.models
        if (mode != "free" or m.free)
        and (m.protocol == protocol or protocol in p.compatible_protocols)
    ]
    if not models:
        raise ValueError(f"No configured model endpoint supports {harness}'s {protocol} API.")
    selected = service.store.account(owner).get("model")
    selected = selected if selected in models else models[0]
    wire = "responses" if harness in {"codex", "codex-native"} else "chat"
    base = service.config.public_url.rstrip("/") + f"/v1/inference/{mode}"
    family = "anthropic" if harness in {"claude-sdk", "claude-native"} else "openai"
    family_config: dict[str, Any] = {
        "base_url": base,
        "auth_command": JOB_AUTH_COMMAND,
        "models": {"default": selected},
    }
    if family == "openai":
        family_config["wire_api"] = wire
    runtime: dict[str, Any] = {
        "providers": {JOB_PROVIDER: {"kind": "gateway", family: family_config}},
        "inference": {
            "harnesses": {
                harness: {
                    "provider": JOB_PROVIDER,
                    "default_model": selected,
                    "model_allowlist": models,
                }
            }
        },
    }
    revision = inference_revision(runtime, {"harness": harness, "owner": owner})
    catalog = {
        "configured": True,
        "configuration_revision": revision,
        "provider_label": "Xwav Free" if mode == "free" else "Xwav subscription",
        "default_model": selected,
        "status": "ready",
        "models": [
            {"id": m, "displayName": m.split("/", 1)[1], "isDefault": m == selected}
            for m in models
        ],
    }
    return {
        "version": 1,
        "target_id": f"sandbox:{target.provider}",
        "configuration_revision": revision,
        "harness": harness,
        "owner_id": owner,
        "runtime_config": runtime,
        "model_discovery": {},
        "connections": {},
        "catalog": catalog,
        "xwav_gateway_job": True,
    }


def is_gateway_job_config(config: dict[str, Any] | None) -> bool:
    return JOB_PROVIDER in (config or {}).get("providers", {})


def job_usage_mode(config: dict[str, Any] | None) -> str:
    from urllib.parse import urlsplit

    provider = (config or {}).get("providers", {}).get(JOB_PROVIDER, {})
    for family in ("openai", "anthropic"):
        base = provider.get(family, {}).get("base_url", "")
        mode = urlsplit(base).path.rstrip("/").rsplit("/", 1)[-1]
        if mode in {"free", "managed"}:
            return mode
    return "free"


def install_job_token(
    launcher: Any, sandbox_id: str, host_id: str, launch_token: str, config: dict[str, Any] | None
) -> None:
    """Install an opaque inference-only token; snapshots contain only a file reference."""
    if not is_gateway_job_config(config):
        return
    from cryptography.fernet import Fernet

    cipher = Fernet(os.environ["XWAV_BILLING_ENCRYPTION_KEY"].encode())
    mode = job_usage_mode(config)
    value = (
        "xwav_job_"
        + cipher.encrypt(
            json.dumps({"host": host_id, "launch": launch_token, "scope": mode}).encode()
        ).decode()
    )
    encoded = base64.b64encode(value.encode()).decode()
    script = (
        'import os,base64,tempfile; from pathlib import Path; p=Path.home()/".omnigent"; '
        "p.mkdir(mode=0o700,exist_ok=True); fd,n=tempfile.mkstemp(dir=p); "
        "os.fchmod(fd,0o600); os.write(fd,base64.b64decode("
        + repr(encoded)
        + ')); os.close(fd); os.replace(n,p/"xwav-job-token")'
    )
    try:
        result = launcher.run(sandbox_id, "python3 -c " + shlex.quote(script))
        if result.returncode:
            raise RuntimeError("Cannot install the job inference credential")
    except Exception:  # noqa: BLE001 - provider errors can echo the credential command
        raise RuntimeError("Cannot install the job inference credential") from None


def job_identity(service: Any, host_store: Any, value: str, mode: str) -> str:
    """Recheck host revocation and expiry; the token authorizes its chosen usage mode only."""
    from cryptography.fernet import InvalidToken
    from fastapi import HTTPException

    try:
        claims = json.loads(service.store.cipher.decrypt(value.removeprefix("xwav_job_").encode()))
        if mode not in {"free", "managed"} or claims["scope"] != mode or host_store is None:
            raise ValueError("scope")
        host = host_store.resolve_launch_token(claims["host"], claims["launch"])
        if host is None or not host.sandbox_provider:
            raise ValueError("revoked")
        return host.user_id
    except (InvalidToken, ValueError, KeyError, TypeError):
        raise HTTPException(401, "Job inference credential expired or revoked") from None


def gateway_terminal_environment(harness: str) -> dict[str, str]:
    """Resolve a job's existing credential for an OpenAI-compatible native client."""
    from pathlib import Path

    from omnigent.inference_config import (
        binding_for_harness,
        load_runtime_inference_config,
        resolve_bound_provider,
    )

    config = load_runtime_inference_config()
    if not is_gateway_job_config(config):
        return {}
    binding = binding_for_harness(config, harness)
    if binding is None or binding.provider != JOB_PROVIDER:
        return {}
    provider = resolve_bound_provider(config, harness)
    family = provider.family("openai") if provider else None
    if family is None or not family.base_url:
        return {}
    value = (Path.home() / ".omnigent" / "xwav-job-token").read_text().strip()
    return {
        "OPENAI_API_KEY": value,
        "OPENAI_BASE_URL": family.base_url,
        "OPENAI_MODEL": binding.default_model or "",
        "QWEN_AUTH_TYPE": "openai",
    }

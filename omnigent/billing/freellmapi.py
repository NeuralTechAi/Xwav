"""Explicit operator connection to a separately installed FreeLLMAPI server."""

from __future__ import annotations

import json
import os
import shlex
import tempfile
from pathlib import Path

import httpx

from omnigent.billing.config import BillingConfig, Model, Provider


def _private_replace(path: Path, content: str) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def connect_freellmapi(
    config_path: Path,
    base_url: str,
    key_file: Path,
    model_ids: tuple[str, ...],
    *,
    auto_model_ids: tuple[str, ...] = (),
    transport: httpx.BaseTransport | None = None,
) -> list[str]:
    """Verify selected available models before updating private local configuration.

    Never import the gateway's whole catalog: it can include disconnected, paid,
    media or multi-model fusion entries. The operator approves each exposed ID.
    """
    config = BillingConfig.model_validate_json(config_path.read_text())
    key = key_file.read_text().strip()
    if not key or any(character in key for character in "\r\n\x00"):
        raise ValueError("A valid private FreeLLMAPI unified key file is required")
    selected = tuple(dict.fromkeys(model_ids))
    if not selected or not any(model not in {"auto", "fusion"} for model in selected):
        raise ValueError("Select at least one approved concrete free model")
    candidates = list(dict.fromkeys(auto_model_ids))
    if candidates and (
        "auto" not in selected
        or set(candidates) - set(selected)
        or {"auto", "fusion"} & set(candidates)
    ):
        raise ValueError("Auto candidates must be selected concrete models, with auto enabled")
    provider = Provider(
        id="free-gateway",
        label="FreeLLMAPI",
        base_url=base_url,
        api_key_env="XWAV_FREE_GATEWAY_KEY",
        compatible_protocols=["chat/completions", "responses", "messages"],
        omit_parallel_tool_calls=True,
        models=[
            Model(
                id=model,
                upstream=model,
                free=True,
                max_output_tokens=2048,
                auto_candidates=candidates if model == "auto" else [],
            )
            for model in selected
        ],
    )
    with httpx.Client(transport=transport, timeout=30, follow_redirects=False) as client:
        response = client.get(
            provider.base_url.rstrip("/") + "/models",
            params={"available": "true"},
            headers={"Authorization": f"Bearer {key}"},
        )
        if response.status_code != 200:
            raise ValueError("FreeLLMAPI model discovery failed; check its URL and unified key")
        catalog = response.json()
        if not isinstance(catalog, dict) or not isinstance(catalog.get("data"), list):
            raise ValueError("FreeLLMAPI returned an invalid model catalog")
        available = {
            row["id"]
            for row in catalog["data"]
            if isinstance(row, dict)
            and isinstance(row.get("id"), str)
            and row.get("available") is not False
        }
    missing = set(selected) - available
    if missing:
        raise ValueError("Selected models are not available from FreeLLMAPI")
    names = {
        row["id"]: row["name"][:200]
        for row in catalog["data"]
        if isinstance(row, dict)
        and isinstance(row.get("id"), str)
        and isinstance(row.get("name"), str)
    }
    for model in provider.models:
        model.label = "Auto" if model.id == "auto" else names.get(model.id, model.id)
    config.providers = [p for p in config.providers if p.id != provider.id] + [provider]
    config = BillingConfig.model_validate(config.model_dump())
    env_path = config_path.parent / "billing.env"
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    lines = [line for line in lines if not line.startswith("XWAV_FREE_GATEWAY_KEY=")]
    lines.append("XWAV_FREE_GATEWAY_KEY=" + shlex.quote(key))
    _private_replace(env_path, "\n".join(lines) + "\n")
    _private_replace(config_path, json.dumps(config.model_dump(), indent=2) + "\n")
    return list(selected)

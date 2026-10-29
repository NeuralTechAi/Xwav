"""Checkpoint transport and session-family serialization for chat file reverts."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

import httpx

from omnigent import workspace_checkpoints
from omnigent.db.workspace_cache import WorkspaceScopedCache

_logger = logging.getLogger(__name__)

_LOCKS: WorkspaceScopedCache[str, asyncio.Lock] = WorkspaceScopedCache()


def history_lock(session_id: str) -> asyncio.Lock:
    if session_id not in _LOCKS:
        _LOCKS[session_id] = asyncio.Lock()
    return _LOCKS[session_id]


def checkpoint_command(
    session_id: str,
    anchor: str,
    action: str,
    token: str | None = None,
    *,
    workspace: str | None = None,
    end_anchor: str | None = None,
    path: str | None = None,
) -> str:
    source = Path(workspace_checkpoints.__file__).read_text()
    parameters = json.dumps(
        {
            "session_id": session_id,
            "anchor": anchor,
            "action": action,
            "token": token,
            "workspace": workspace,
            "end_anchor": end_anchor,
            "path": path,
            "storage_root": os.environ.get("OMNIGENT_CHECKPOINT_ROOT"),
        }
    )
    return (
        "python3 - <<'XWAV_FILE_CHECKPOINT'\n"
        + source
        + "\nprint(json.dumps(checkpoint_request(json.loads("
        + repr(parameters)
        + "))))\nXWAV_FILE_CHECKPOINT"
    )


async def capture_before_message(
    client: httpx.AsyncClient, session_id: str, anchor: str, *, workspace: str | None = None
) -> None:
    """Best effort on unsupported runners; never pretend a missing snapshot exists."""
    try:
        status = await client.get(f"/v1/sessions/{session_id}", timeout=3)
        payload = status.json() if status.status_code == 200 else None
        if not isinstance(payload, dict) or payload.get("status") not in {"idle", "failed"}:
            _logger.info("File checkpoint skipped for session %s: status %s", session_id, payload)
            return
        result = await client.post(
            f"/v1/sessions/{session_id}/resources/environments/default/shell",
            json={
                "command": checkpoint_command(session_id, anchor, "capture", workspace=workspace),
                "timeout": 25,
            },
            timeout=30,
        )
        if result.status_code == 200:
            shell = result.json()
            if not isinstance(shell, dict) or not isinstance(shell.get("stdout"), str):
                return
            output = json.loads(shell["stdout"].strip().splitlines()[-1])
            if isinstance(output, dict) and output.get("state") != "ready":
                _logger.info(
                    "File checkpoint unavailable for session %s: %s",
                    session_id,
                    output.get("message"),
                )
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError):
        return

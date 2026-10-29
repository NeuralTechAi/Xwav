"""Owner-scoped Strix jobs: prepare a disposable snapshot, then run an isolated CLI worker."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from collections.abc import Awaitable, Callable
from contextlib import suppress
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from fastapi import HTTPException

from omnigent.billing.failover import _zero_cost
from omnigent.db.workspace_cache import WorkspaceScopedCache
from omnigent.penetration_runtime import inspect_reports

# custom-lint: disable-next=workspace-scoped-cache -- set of globally unique Task objects
_TASKS: set[asyncio.Task] = set()
_LOCKS: WorkspaceScopedCache[str, asyncio.Lock] = WorkspaceScopedCache()


def service_root() -> Path:
    return Path(
        os.environ.get("XWAV_STRIX_RUNTIME_ROOT", Path.cwd() / ".omnigent/services/strix")
    ).resolve()


def session_directory(session_id: str) -> Path:
    return service_root() / "jobs" / hashlib.sha256(session_id.encode()).hexdigest()


def save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value))
    temporary.chmod(0o600)
    temporary.replace(path)


def extract_snapshot(archive: BinaryIO, target: Path) -> None:
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        total = 0
        for index, entry in enumerate(source.infolist()):
            relative = PurePosixPath(entry.filename)
            if (
                index >= 20000
                or relative.is_absolute()
                or ".." in relative.parts
                or "\\" in entry.filename
                or (entry.external_attr >> 16) & 0o170000 == 0o120000
            ):
                raise ValueError("Unsafe project snapshot")
            if any(part in {".omnigent", "strix_runs", ".xwav"} for part in relative.parts):
                continue
            total += entry.file_size
            if total > 512 * 1024 * 1024:
                raise ValueError("Project snapshot exceeds 512 MiB")
            destination = target.joinpath(*relative.parts)
            if entry.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with source.open(entry) as incoming, destination.open("wb") as output:
                    shutil.copyfileobj(incoming, output)


def _state(directory: Path) -> dict:
    return json.loads((directory / "state.json").read_text())


def failure_detail(directory: Path) -> str:
    """Classify bounded logs without returning upstream bodies, code or secrets."""
    try:
        with (directory / "engine.log").open("rb") as log:
            log.seek(0, 2)
            log.seek(max(0, log.tell() - 16384))
            tail = log.read(16384).decode(errors="replace")
    except OSError:
        tail = ""
    if "Model provider rejected the request (400)" in tail or "Error code: 400" in tail:
        return (
            "The model rejected Strix's tool request (HTTP 400). "
            "Check model tool compatibility and run again. No completed assessment is available."
        )
    if "All configured free models" in tail or "Error code: 424" in tail:
        return (
            "The configured free model pool has no capacity available. "
            "Wait for its rate limits to reset, then run again. No paid model was used."
        )
    if "LLM_PREFLIGHT_TIMEOUT" in tail or "APITimeoutError" in tail:
        return (
            "The model did not respond within the request limit. "
            "Run again when capacity is available."
        )
    if "Cannot connect to the Docker daemon" in tail or "Docker is not running" in tail:
        return "Docker is unavailable. Start the local Docker service, then run again."
    return (
        "Strix stopped before completing the assessment. Partial findings remain available below."
    )


def report(session_id: str, run: str | None = None) -> dict | None:
    root = session_directory(session_id)
    if not (root / "latest").exists():
        return None
    run_id = run or (root / "latest").read_text()
    if len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
        return None  # Legacy Strix runs are still read from the job workspace.
    directory = root / run_id
    if not (directory / "state.json").is_file():
        return None
    state = _state(directory)
    if state["state"] == "running" and time.time() - state.get("heartbeat", 0) > 120:
        state.update(state="error", error="Scan worker stopped responding. Run again.")
        save(directory / "state.json", state)
    if state["state"] == "error" and state.get("error", "").startswith("Strix could not complete"):
        state.update(error=failure_detail(directory), phase="Scan failed")
    result = inspect_reports(str(directory))
    result.update(
        state=state["state"],
        phase=state.get("phase", ""),
        managed=True,
        strix_installed=True,
        scope="entire project",
        error=state.get("error"),
    )
    result["run"] = {
        **result.get("run", {}),
        "id": run_id,
        "started_at": state.get("started_at", ""),
        "mode": "standard · full project",
    }
    result["runs"] = [
        {"id": p.name, "updated_at": p.stat().st_mtime}
        for p in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        if p.is_dir() and (p / "state.json").is_file()
    ][:100]
    return result


def scan_identity(service: Any, value: str, mode: str) -> str:
    from cryptography.fernet import InvalidToken

    try:
        claims = json.loads(
            service.store.cipher.decrypt(value.removeprefix("xwav_scan_").encode())
        )
        if mode != "free" or claims["expires"] < time.time():
            raise ValueError("Expired scan")
        directory = session_directory(claims["session"]) / claims["run"]
        if _state(directory)["state"] != "running" or (directory / "cancel").exists():
            raise ValueError("Scan stopped")
        return claims["owner"]
    except (InvalidToken, OSError, ValueError, KeyError, TypeError):
        raise HTTPException(401, "Scan model credential expired or revoked") from None


async def action(
    session_id: str,
    owner: str,
    operation: str,
    service: Any,
    snapshot: Callable[[], Awaitable[BinaryIO]],
) -> dict:
    if session_id not in _LOCKS:
        _LOCKS[session_id] = asyncio.Lock()
    lock = _LOCKS[session_id]
    async with lock:
        existing = report(session_id)
        if operation == "cancel":
            if existing and existing["state"] == "running":
                (session_directory(session_id) / existing["run"]["id"] / "cancel").touch()
            return existing or {"state": "empty", "runs": [], "findings": []}
        if existing and (operation == "ensure" or existing["state"] == "running"):
            return existing
        if service is None:
            raise HTTPException(503, "Configure Xwav's free model gateway before starting Strix")
        ready = [
            (p, m)
            for p in service.config.providers
            for m in p.models
            if _zero_cost(m)
            and os.getenv(p.api_key_env)
            and (m.protocol == "chat/completions" or "chat/completions" in p.compatible_protocols)
        ]
        if not ready:
            raise HTTPException(503, "No zero-cost model is configured for Strix")
        selected = next(((p, m) for p, m in ready if m.auto_candidates), ready[0])
        run_id = uuid.uuid4().hex
        directory = session_directory(session_id) / run_id
        directory.mkdir(mode=0o700, parents=True)
        save(
            directory / "state.json",
            {
                "state": "running",
                "phase": "Preparing project snapshot",
                "heartbeat": time.time(),
                "started_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            },
        )
        (directory.parent / "latest").write_text(run_id)
        credential = (
            "xwav_scan_"
            + service.store.cipher.encrypt(
                json.dumps(
                    {
                        "owner": owner,
                        "session": session_id,
                        "run": run_id,
                        "expires": time.time() + 3600,
                    }
                ).encode()
            ).decode()
        )
        save(
            directory / "private.json",
            {
                "token": credential,
                "base_url": service.config.public_url.rstrip("/") + "/v1/inference/free",
                "model": f"{selected[0].id}/{selected[1].id}",
                "runtime_root": str(service_root()),
                "executable": os.environ.get("XWAV_STRIX_EXECUTABLE", ""),
            },
        )

        async def prepare() -> None:
            async def heartbeat() -> None:
                while True:
                    await asyncio.sleep(5)
                    current = _state(directory)
                    current["heartbeat"] = time.time()
                    save(directory / "state.json", current)

            pulse = asyncio.create_task(heartbeat())
            try:
                archive = await snapshot()
                try:
                    await asyncio.to_thread(extract_snapshot, archive, directory / "source")
                finally:
                    archive.close()
                if (directory / "cancel").exists():
                    state = _state(directory)
                    state.update(state="stopped", phase="Cancelled")
                    (directory / "private.json").unlink(missing_ok=True)
                    shutil.rmtree(directory / "source", ignore_errors=True)
                    save(directory / "state.json", state)
                    return
                pulse.cancel()
                with suppress(asyncio.CancelledError):
                    await pulse
                with (directory / "worker.log").open("wb") as log:
                    subprocess.Popen(
                        [sys.executable, "-m", "omnigent.penetration_worker", str(directory)],
                        stdin=subprocess.DEVNULL,
                        stdout=log,
                        stderr=log,
                        start_new_session=True,
                        env={
                            "PATH": os.environ.get("PATH", os.defpath),
                            "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
                            **(
                                {"DOCKER_HOST": os.environ["DOCKER_HOST"]}
                                if os.getenv("DOCKER_HOST")
                                else {}
                            ),
                        },
                    )
            except BaseException:  # noqa: BLE001 -- persist cancellation/failure without leaking gateway credentials
                state = _state(directory)
                state.update(
                    state="error",
                    error="Could not prepare this project for scanning. "
                    "Resume the job and run again.",
                )
                (directory / "private.json").unlink(missing_ok=True)
                shutil.rmtree(directory / "source", ignore_errors=True)
                save(directory / "state.json", state)
            finally:
                pulse.cancel()
                with suppress(asyncio.CancelledError):
                    await pulse

        task = asyncio.create_task(prepare())
        _TASKS.add(task)
        task.add_done_callback(_TASKS.discard)
        return report(session_id) or {}

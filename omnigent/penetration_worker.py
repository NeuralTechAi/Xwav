"""On-demand Strix installation and bounded full-project CLI execution."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path

from omnigent.penetration_runtime import inspect_reports
from omnigent.server.strix_jobs import _state, failure_detail, save


def execute(
    command: list[str], directory: Path, env: dict[str, str], phase: str, timeout: int
) -> int:
    state = _state(directory)
    state.update(phase=phase, heartbeat=time.time())
    save(directory / "state.json", state)
    with (directory / "engine.log").open("ab") as log:
        process = subprocess.Popen(
            command,
            cwd=directory,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
        started = time.monotonic()
        while process.poll() is None:
            state.update(heartbeat=time.time())
            save(directory / "state.json", state)
            if (directory / "cancel").exists() or time.monotonic() - started > timeout:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                return -1
            time.sleep(1)
        return process.returncode


def worker(directory: Path) -> None:
    settings = json.loads((directory / "private.json").read_text())
    (directory / "private.json").unlink()
    home = directory / "home"
    home.mkdir(mode=0o700)
    env = {
        "PATH": os.environ.get("PATH", os.defpath),
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "PYTHONUNBUFFERED": "1",
        "STRIX_TELEMETRY": "0",
        "OTEL_SDK_DISABLED": "true",
    }
    if os.getenv("DOCKER_HOST"):
        env["DOCKER_HOST"] = os.environ["DOCKER_HOST"]
    state = _state(directory)
    try:
        executable = settings.get("executable")
        if not executable:
            runtime = Path(settings["runtime_root"])
            runtime.mkdir(parents=True, exist_ok=True)
            with (runtime / "install.lock").open("w") as lock:
                while True:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        state.update(heartbeat=time.time(), phase="Waiting for shared Strix setup")
                        save(directory / "state.json", state)
                        if (directory / "cancel").exists():
                            raise RuntimeError("Scan cancelled") from None
                        time.sleep(1)
                executable = str(runtime / "venv/bin/strix")
                if not Path(executable).exists():
                    if (
                        execute(
                            [sys.executable, "-m", "venv", str(runtime / "venv")],
                            directory,
                            env,
                            "Setting up Strix runtime",
                            120,
                        )
                        != 0
                    ):
                        raise RuntimeError("Strix Python environment setup failed")
                    if (
                        execute(
                            [
                                str(runtime / "venv/bin/python"),
                                "-m",
                                "pip",
                                "install",
                                "--disable-pip-version-check",
                                "strix-agent==1.7.0",
                                "litellm==1.106.4",
                            ],
                            directory,
                            env,
                            "Installing Strix once",
                            600,
                        )
                        != 0
                    ):
                        raise RuntimeError(
                            "Strix installation failed; check the server's package network access"
                        )
        # Strix receives only this run's revocable inference credential.
        env.update(
            STRIX_LLM="openai/" + settings["model"],
            LLM_API_KEY=settings["token"],
            LLM_API_BASE=settings["base_url"],
            STRIX_API_TYPE="chat_completions",
            LLM_TIMEOUT="150",
            # Xwav's free-pool failover can take up to 120 seconds. Strix's
            # 30-second default would abort a healthy fallback during startup.
            LLM_PREFLIGHT_TIMEOUT="150",
            STRIX_DISABLE_UPDATE_CHECK="1",
            STRIX_RUN_ID="xwav-" + directory.name,
            STRIX_RUN_TYPE="xwav-local",
        )
        instructions = directory / "scope.txt"
        instructions.write_text(
            "Assess the entire supplied local project, not only changed files. "
            "Scope is this disposable source tree and local services you start for it. "
            "Do not attack remote URLs, production systems, host services "
            "or third-party dependencies. Do not include secret values in findings. "
            "Call at most one tool at a time. "
            "Record evidence and remediation in Strix reports."
        )
        code = execute(
            [
                executable,
                "-n",
                "--target",
                str(directory / "source"),
                "--scope-mode",
                "full",
                "--scan-mode",
                "standard",
                "--max-budget",
                "1",
                "--max-turns",
                "20",
                "--instruction-file",
                str(instructions),
            ],
            directory,
            env,
            "Scanning the entire project with Strix",
            1800,
        )
        state = _state(directory)
        if (directory / "cancel").exists():
            state.update(state="stopped", phase="Cancelled")
        elif code in {0, 2} and inspect_reports(str(directory))["state"] == "complete":
            state.update(state="complete", phase="Strix finished")
        elif code == -1:
            state.update(
                state="stopped",
                phase="Time limit reached",
                error="Scan reached its 30-minute limit. "
                "Partial results are not a completed assessment.",
            )
        else:
            state.update(
                state="error",
                phase="Scan failed",
                error=failure_detail(directory),
                exit_code=code,
            )
    except Exception as error:  # noqa: BLE001 -- worker boundary must redact credentials in upstream errors
        state = _state(directory)
        state.update(
            state="error",
            error=str(error)
            if isinstance(error, RuntimeError)
            else "Strix runtime setup failed. Run again.",
        )
    finally:
        if (directory / "cancel").exists():
            state.update(state="stopped", phase="Cancelled", error=None)
        shutil.rmtree(directory / "source", ignore_errors=True)
        # Reap only sandboxes labeled by this specific Xwav run, including after
        # forced termination. Never stop other jobs or user-owned containers.
        with suppress(OSError, subprocess.SubprocessError):
            containers = subprocess.run(
                [
                    "docker",
                    "ps",
                    "-aq",
                    "--filter",
                    f"label=strix-run-id=xwav-{directory.name}",
                    "--filter",
                    "label=strix-run-type=xwav-local",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
                check=True,
            ).stdout.split()
            if containers and all(all(c in "0123456789abcdef" for c in cid) for cid in containers):
                subprocess.run(
                    ["docker", "rm", "-f", *containers],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15,
                    env=env,
                    check=False,
                )
        state.update(heartbeat=time.time())
        save(directory / "state.json", state)


if __name__ == "__main__":
    worker(Path(sys.argv[1]).resolve())

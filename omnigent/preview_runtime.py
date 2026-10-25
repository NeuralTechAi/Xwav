"""Workspace-local preview discovery; also sent to existing runners over their shell API."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil

_IGNORED = {"node_modules", ".git", ".venv", "venv", ".next", "dist", "build", "__pycache__"}


def source_version(root: Path, *, include_build_output: bool = False) -> str:
    """Bounded metadata scan, excluding generated content and symlinks."""
    digest = hashlib.sha256()
    count = 0
    for directory, dirs, files in os.walk(root):
        dirs[:] = sorted(
            name
            for name in dirs
            if (name not in _IGNORED or (include_build_output and name in {"dist", "build"}))
            and not name.startswith(".")
        )
        for name in sorted(files):
            path = Path(directory) / name
            if path.is_symlink():
                continue
            try:
                stat = path.stat()
                digest.update(
                    f"{path.relative_to(root)}:{stat.st_mtime_ns}:{stat.st_size}".encode()
                )
            except OSError:
                continue
            count += 1
            if count >= 3000:
                return digest.hexdigest()[:20]
    return digest.hexdigest()[:20]


def launch_command(root: Path, port: int) -> tuple[list[str], str] | None:
    """Select only recognizable development runtimes; never install dependencies."""
    config_path = root / ".xwav" / "preview.json"
    if config_path.is_file():
        config = json.loads(config_path.read_text())
        command = config.get("command")
        if isinstance(command, list) and command and all(isinstance(arg, str) for arg in command):
            return [arg.replace("{port}", str(port)) for arg in command], "reload"
    static_directory = next(
        (
            root / name
            for name in (".", "dist", "build", "public")
            if (root / name / "index.html").is_file()
        ),
        None,
    )
    static_command = (
        [
            sys.executable,
            "-m",
            "http.server",
            str(port),
            "--bind",
            "127.0.0.1",
            "--directory",
            str(static_directory),
        ]
        if static_directory is not None
        else None
    )
    manifest = root / "package.json"
    if manifest.is_file():
        package = json.loads(manifest.read_text())
        scripts = package.get("scripts", {})
        script = "dev" if scripts.get("dev") else "start" if scripts.get("start") else None
        if script is None:
            return (static_command, "reload") if static_command is not None else None
        manager = next(
            (
                tool
                for lock, tool in [
                    ("pnpm-lock.yaml", "pnpm"),
                    ("yarn.lock", "yarn"),
                    ("bun.lock", "bun"),
                ]
                if (root / lock).exists() and shutil.which(tool)
            ),
            "npm",
        )
        command = [manager, "run", script]
        definition = str(scripts[script])
        args: list[str] = []
        if "next" in definition:
            args = ["--hostname", "127.0.0.1", "--port", str(port)]
        elif any(tool in definition for tool in ("vite", "astro", "nuxt")):
            args = ["--host", "127.0.0.1", "--port", str(port)]
        elif "expo" in definition:
            args = ["--web", "--port", str(port)]
        if args:
            command += ([] if manager in {"yarn", "bun"} else ["--"]) + args
        return command, "hot" if any(
            tool in definition
            for tool in ("vite", "next", "astro", "nuxt", "expo", "react-scripts")
        ) else "reload"
    if static_command is not None:
        return static_command, "reload"
    return None


def app_directory(workspace: Path) -> Path | None:
    """Use a single runnable app, including projects created in a workspace subfolder."""
    if launch_command(workspace, 0) is not None:
        return workspace
    candidates: list[Path] = []
    visited = 0
    for directory, dirs, _files in os.walk(workspace):
        current = Path(directory)
        dirs[:] = sorted(
            name
            for name in dirs
            if name not in _IGNORED
            and not name.startswith(".")
            and not (current / name).is_symlink()
        )
        if len(current.relative_to(workspace).parts) >= 3:
            dirs[:] = []
        visited += 1
        if visited > 100:
            return None
        if current == workspace:
            continue
        if launch_command(current, 0) is not None:
            candidates.append(current)
            # Do not count public/index.html or examples inside an app as extra apps.
            dirs[:] = []
            if len(candidates) > 1:
                return None
    return candidates[0] if candidates else None


def workspace_ports(root: Path) -> list[int]:
    """Only consider listeners owned by a process running in this workspace."""
    ports: set[int] = set()
    for process in psutil.process_iter():
        try:
            cwd = Path(process.cwd()).resolve()
            if cwd != root and not cwd.is_relative_to(root):
                continue
            args = process.cmdline()
            if any(
                "omnigent.runner" in arg or "omnigent.cli" in arg or "omnigent.harnesses" in arg
                for arg in args
            ):
                continue
            if any(
                Path(arg).name in {"omnigent", "omni", "xwav", "codex", "claude"}
                for arg in args[:2]
            ):
                continue
            connections = getattr(process, "net_connections", None) or process.connections
            for connection in connections(kind="tcp"):
                if connection.status == psutil.CONN_LISTEN and connection.laddr:
                    ports.add(connection.laddr.port)
        except (psutil.Error, OSError):
            continue
    return sorted(ports)


def http_ready(port: int, *, revision_query: bool = False) -> bool:
    """Require a renderable HTML page, never an API or WebSocket error response."""
    import urllib.error
    import urllib.request

    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        suffix = "?__xwav_preview_revision=probe" if revision_query else ""
        with opener.open(f"http://127.0.0.1:{port}/{suffix}", timeout=0.3) as response:
            content_type = response.headers.get_content_type()
            return 200 <= response.status < 300 and content_type in {
                "text/html",
                "application/xhtml+xml",
            }
    except urllib.error.HTTPError:
        return False
    except (OSError, ValueError):
        return False


def preview(start: bool = True) -> dict[str, object]:
    root = Path.cwd().resolve()
    if root == Path(root.anchor) or root == Path.home():
        return {"state": "waiting", "message": "Select a project workspace to preview its app."}
    storage = Path(tempfile.gettempdir()) / f"xwav-preview-{os.getuid()}"
    storage.mkdir(mode=0o700, exist_ok=True)
    key = hashlib.sha256(str(root).encode()).hexdigest()
    record_path = storage / f"{key}.json"
    with (storage / f"{key}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            record = json.loads(record_path.read_text())
        except (OSError, ValueError):
            record = {}
        version = source_version(root, include_build_output=True)
        if record.get("port") and record.get("pid"):
            try:
                process = psutil.Process(record["pid"])
                alive = (
                    abs(process.create_time() - record["created"]) < 0.1
                    and process.is_running()
                    and process.status() != psutil.STATUS_ZOMBIE
                )
            except psutil.Error:
                alive = False
            if alive:
                ready = http_ready(record["port"])
                if not ready:
                    for candidate in workspace_ports(root):
                        if http_ready(candidate):
                            record["port"] = candidate
                            record_path.write_text(json.dumps(record))
                            ready = True
                            break
                return {
                    "state": "ready" if ready else "starting",
                    "port": record["port"],
                    "revision_query": ready and http_ready(record["port"], revision_query=True),
                    "version": version if record["mode"] != "hot" else str(record["created"]),
                    "mode": record["mode"],
                    "message": "Live project preview" if ready else "Starting the project’s app…",
                }
        for port in workspace_ports(root):
            if http_ready(port):
                selected = launch_command(root, port)
                mode = selected[1] if selected else "reload"
                return {
                    "state": "ready",
                    "port": port,
                    "revision_query": http_ready(port, revision_query=True),
                    "version": f"existing:{port}" if mode == "hot" else version,
                    "mode": mode,
                    "message": "Connected to this project’s running app",
                }
        if record and time.time() - record.get("started", 0) < 20:
            return {
                "state": "error",
                "message": "The app server exited. Check its dependencies; preview will retry.",
            }
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        directory = app_directory(root)
        selected = launch_command(directory, port) if directory is not None else None
        if selected is None:
            return {
                "state": "waiting",
                "message": (
                    "Waiting for one runnable web app in this job. "
                    "For multiple apps, choose one in .xwav/preview.json."
                ),
            }
        if not start:
            return {"state": "waiting", "message": "The project preview has not started."}
        command, mode = selected
        environment = {**os.environ, "PORT": str(port), "HOST": "127.0.0.1", "BROWSER": "none"}
        with (storage / f"{key}.log").open("w") as log:
            process = subprocess.Popen(
                command,
                cwd=directory,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        record = {
            "pid": process.pid,
            "created": psutil.Process(process.pid).create_time(),
            "port": port,
            "mode": mode,
            "started": time.time(),
        }
        record_path.write_text(json.dumps(record))
        return {"state": "starting", "message": "Starting the project’s app…"}


if __name__ == "__main__":
    try:
        print(json.dumps(preview()))
    except (OSError, ValueError, KeyError, TypeError, psutil.Error):
        print(
            json.dumps(
                {
                    "state": "error",
                    "message": (
                        "Preview could not start this project’s app. "
                        "Check its development runtime and dependencies."
                    ),
                }
            )
        )

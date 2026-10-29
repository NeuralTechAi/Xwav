"""Automatic previews use separate workspace processes and detect source changes."""

import json

import httpx
import psutil
import pytest

from omnigent import preview_runtime as runtime
from tests._helpers.polling import poll_until


def test_manifest_command_preserves_manager_and_framework_flags(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}))
    command, mode = runtime.launch_command(tmp_path, 41234)
    assert command == ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "41234"]
    assert mode == "hot"
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "next dev"}}))
    command, _ = runtime.launch_command(tmp_path, 41234)
    assert "--hostname" in command and "--host" not in command


@pytest.mark.parametrize("script", ["electron .", "npx electron-forge start", "electronmon ."])
def test_desktop_launch_uses_browser_renderer_instead_of_native_window(tmp_path, script):
    renderer = tmp_path / "src"
    renderer.mkdir()
    (renderer / "index.html").write_text("<h1>Renderer</h1>")
    manifest = tmp_path / "package.json"
    manifest.write_text(json.dumps({"scripts": {"start": script}}))
    command, mode = runtime.launch_command(tmp_path, 41234)
    assert command[-2:] == ["--directory", str(renderer)]
    assert "http.server" in command and mode == "reload"
    # A dedicated browser development script still takes precedence.
    manifest.write_text(json.dumps({"scripts": {"start": script, "dev": "vite"}}))
    assert runtime.launch_command(tmp_path, 41234)[0][:3] == ["npm", "run", "dev"]
    manifest.write_text(json.dumps({"scripts": {"start": script}}))
    (renderer / "index.html").unlink()
    assert runtime.launch_command(tmp_path, 41234) is None


def test_source_version_ignores_generated_dependencies_and_links(tmp_path):
    (tmp_path / "index.html").write_text("first")
    before = runtime.source_version(tmp_path)
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "generated").write_text("ignore")
    assert runtime.source_version(tmp_path) == before
    (tmp_path / "index.html").write_text("updated source")
    assert runtime.source_version(tmp_path) != before


def test_two_live_apps_are_automatic_isolated_and_reused(tmp_path, monkeypatch):
    storage = tmp_path / "runtime"
    storage.mkdir()
    monkeypatch.setattr(runtime.tempfile, "gettempdir", lambda: str(storage))
    workspaces = [tmp_path / name for name in ("alpha", "beta")]
    try:
        results = []
        for workspace in workspaces:
            workspace.mkdir()
            (workspace / "index.html").write_text(f"<h1>{workspace.name}</h1>")
            monkeypatch.chdir(workspace)
            assert runtime.preview()["state"] == "starting"
            poll_until(lambda: runtime.preview()["state"] == "ready", timeout_s=15, interval_s=0.1)
            result = runtime.preview()
            results.append(result)
            assert result["revision_query"] is True
            assert runtime.preview()["port"] == result["port"]
            assert (
                workspace.name
                in httpx.get(f"http://127.0.0.1:{result['port']}", trust_env=False).text
            )
        assert results[0]["port"] != results[1]["port"]
        (workspaces[1] / "index.html").write_text("<h1>Changed live</h1>")
        changed = runtime.preview()
        assert changed["port"] == results[1]["port"]
        assert changed["version"] != results[1]["version"]
        assert (
            "Changed live"
            in httpx.get(f"http://127.0.0.1:{changed['port']}", trust_env=False).text
        )
    finally:
        for record_path in storage.rglob("*.json"):
            record = json.loads(record_path.read_text())
            try:
                process = psutil.Process(record["pid"])
                if abs(process.create_time() - record["created"]) < 0.1:
                    process.terminate()
                    process.wait(5)
            except psutil.NoSuchProcess:
                pass


@pytest.mark.parametrize(
    "status,content_type,expected",
    [
        (200, "text/html; charset=utf-8", True),
        (200, "application/xhtml+xml", True),
        (200, "application/json", False),
        (200, "text/plain", False),
        (204, "", False),
        (400, "text/plain", False),
        (404, "text/html", False),
        (426, "text/plain", False),
        (503, "text/html", False),
    ],
)
def test_preview_requires_successful_html_response(monkeypatch, status, content_type, expected):
    import urllib.error
    from email.message import Message
    from io import BytesIO
    from unittest.mock import MagicMock

    headers = Message()
    headers["Content-Type"] = content_type
    opener = MagicMock()
    if status >= 400:
        opener.open.side_effect = urllib.error.HTTPError(
            "http://127.0.0.1:41234/",
            status,
            "not an app",
            headers,
            BytesIO(b"Connection header did not include 'upgrade'"),
        )
    else:
        response = opener.open.return_value.__enter__.return_value
        response.status = status
        response.headers = headers
    monkeypatch.setattr("urllib.request.build_opener", lambda *args: opener)
    assert runtime.http_ready(41234) is expected


def test_websocket_listener_does_not_prevent_automatic_app_start(tmp_path, monkeypatch):
    """A real workspace-owned websocket endpoint must not win over the HTML app."""
    import subprocess
    import sys

    storage = tmp_path / "runtime"
    storage.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    app = workspace / "simple-app"
    app.mkdir()
    (app / "package.json").write_text(json.dumps({"scripts": {"test": "node --test"}}))
    output = app / "dist"
    output.mkdir()
    (output / "index.html").write_text("<h1>The actual project app</h1>")
    listener = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-c",
            """
from http.server import BaseHTTPRequestHandler, HTTPServer
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(400)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Connection header did not include 'upgrade'")
    def log_message(self, *args): pass
server=HTTPServer(('127.0.0.1',0),Handler)
print(server.server_port,flush=True)
server.serve_forever()
""",
        ],
        cwd=workspace,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert listener.stdout is not None
        websocket_port = int(listener.stdout.readline())
        monkeypatch.setattr(runtime.tempfile, "gettempdir", lambda: str(storage))
        monkeypatch.chdir(workspace)
        assert websocket_port in runtime.workspace_ports(workspace)
        assert not runtime.http_ready(websocket_port)
        assert runtime.preview()["state"] == "starting"
        poll_until(lambda: runtime.preview()["state"] == "ready", timeout_s=15, interval_s=0.1)
        ready = runtime.preview()
        assert ready["port"] != websocket_port
        assert (
            "The actual project app"
            in httpx.get(
                f"http://127.0.0.1:{ready['port']}/",
                trust_env=False,
            ).text
        )
        (output / "index.html").write_text("<h1>Updated built app</h1>")
        assert runtime.preview()["version"] != ready["version"]
        # A previously cached wrong port must also heal to the real HTML listener.
        record_path = next(storage.rglob("*.json"))
        record = json.loads(record_path.read_text())
        record["port"] = websocket_port
        record_path.write_text(json.dumps(record))
        assert runtime.preview()["port"] == ready["port"]
    finally:
        listener.terminate()
        listener.wait(5)
        for record_path in storage.rglob("*.json"):
            record = json.loads(record_path.read_text())
            try:
                process = psutil.Process(record["pid"])
                if abs(process.create_time() - record["created"]) < 0.1:
                    process.terminate()
                    process.wait(5)
            except psutil.NoSuchProcess:
                pass


def test_app_directory_prefers_root_and_does_not_guess_between_apps(tmp_path):
    first = tmp_path / "first-app"
    first.mkdir()
    (first / "index.html").write_text("first")
    assert runtime.app_directory(tmp_path) == first
    second = tmp_path / "second-app"
    second.mkdir()
    (second / "index.html").write_text("second")
    assert runtime.app_directory(tmp_path) is None
    (tmp_path / "index.html").write_text("workspace app")
    assert runtime.app_directory(tmp_path) == tmp_path


def test_app_directory_ignores_dependency_and_symlink_projects(tmp_path):
    dependencies = tmp_path / "node_modules" / "example"
    dependencies.mkdir(parents=True)
    (dependencies / "index.html").write_text("dependency example")
    (tmp_path / "linked-app").symlink_to(dependencies, target_is_directory=True)
    assert runtime.app_directory(tmp_path) is None


def test_preview_detects_query_intolerant_servers(tmp_path, monkeypatch):
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class ExactPathServer(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/" else 404)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Exact path app</h1>")

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), ExactPathServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_port
        assert runtime.http_ready(port)
        assert not runtime.http_ready(port, revision_query=True)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(runtime, "workspace_ports", lambda _root: [port])
        result = runtime.preview()
        assert result["state"] == "ready"
        assert result["port"] == port and result["revision_query"] is False
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)

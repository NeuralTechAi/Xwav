"""Real HTTP traffic, bounded profiles and persistent load-report transport."""

import asyncio
import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import psutil
import pytest

from omnigent import loadtesting_runtime as runtime
from omnigent.server.loadtesting import loadtesting_command
from tests._helpers.polling import poll_until


@pytest.fixture
def service():
    agents = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            agents.append(self.headers.get("User-Agent"))
            self.send_response(500 if self.path == "/fail" else 200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>fixture</h1>")

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_port, agents
    server.shutdown()
    server.server_close()
    thread.join(5)


def config(root, **changes):
    (root / ".xwav").mkdir(exist_ok=True)
    data = {"durations": dict.fromkeys(runtime.PROFILES, 1), **changes}
    (root / ".xwav/loadtesting.json").write_text(json.dumps(data))
    return runtime.settings(root)


@pytest.mark.parametrize(
    "changes",
    [
        {"concurrency": 17},
        {"requests_per_second": 51},
        {"max_requests": True},
        {"durations": {"soak": 1801}},
        {"paths": ["//example.com"]},
        {"paths": ["/\r\nHost: example.com"]},
        {"paths": ["https://example.com"]},
        {"paths": ["/\u2603"]},
        {"concurrency": 4, "max_concurrency": 2},
    ],
)
def test_invalid_traffic_configuration_cannot_run(tmp_path, changes):
    with pytest.raises(ValueError):
        config(tmp_path, **changes)


def test_profiles_change_concurrency_and_actual_request_rate(tmp_path):
    cfg = runtime.settings(tmp_path)
    assert runtime.concurrency("stress", 0, cfg) < runtime.concurrency("stress", 0.99, cfg)
    assert runtime.traffic_rate("stress", 0, cfg) < runtime.traffic_rate("stress", 0.99, cfg)
    assert runtime.traffic_rate("spike", 0.4, cfg) > runtime.traffic_rate("spike", 0.1, cfg)
    assert runtime.traffic_rate("spike", 0.8, cfg) == runtime.traffic_rate("spike", 0.1, cfg)
    assert runtime.concurrency("spike", 0.4, cfg) > runtime.concurrency("spike", 0.8, cfg)
    assert runtime.percentile([1, 2, 3, 4, 100], 0.95) == 100


def test_real_traffic_metrics_and_platform_samples(service, tmp_path):
    port, agents = service
    cfg = config(tmp_path)
    snapshots = []
    result = asyncio.run(
        runtime.measure(
            port, "load", cfg, tmp_path / "cancel", snapshots.append, {"remaining": 100, "sent": 0}
        )
    )
    assert result["status"] == "passed"
    metrics = result["metrics"]
    assert 5 <= metrics["requests"] <= 21 and metrics["errors"] == 0
    assert metrics["p99_ms"] >= metrics["p50_ms"] > 0
    assert metrics["peak_concurrency"] <= cfg["concurrency"]
    assert all(row["requests"] > 0 for row in metrics["platforms"].values())
    assert snapshots and metrics["series"]
    assert metrics["series"][-1]["requests"] == metrics["requests"]
    assert any("Android" in agent for agent in agents)
    assert any("iPhone" in agent for agent in agents)


def test_failures_budget_and_cancellation_remain_visible(service, tmp_path):
    port, _ = service
    cfg = config(tmp_path, paths=["/fail"])
    result = asyncio.run(
        runtime.measure(
            port, "load", cfg, tmp_path / "cancel", lambda _: None, {"remaining": 100, "sent": 0}
        )
    )
    assert result["status"] == "failed" and result["metrics"]["error_percent"] == 100
    cfg = config(tmp_path)
    limited = asyncio.run(
        runtime.measure(
            port, "load", cfg, tmp_path / "cancel", lambda _: None, {"remaining": 1, "sent": 0}
        )
    )
    assert limited["status"] == "blocked" and limited["metrics"]["requests"] == 1

    async def cancelled():
        asyncio.get_running_loop().call_later(0.1, (tmp_path / "cancel").touch)
        return await runtime.measure(
            port, "soak", cfg, tmp_path / "cancel", lambda _: None, {"remaining": 100, "sent": 0}
        )

    result = asyncio.run(cancelled())
    assert result["status"] == "cancelled" and result["metrics"]["duration"] < 3


def test_transport_persists_reports_and_does_not_share_preproduction(tmp_path, monkeypatch):
    monkeypatch.setenv("XWAV_TEST_REPORT_ROOT", str(tmp_path / "reports"))
    root = tmp_path / "project"
    root.mkdir()
    (root / "index.html").write_text("<!doctype html><title>App</title><h1>App</h1>")
    config(root)

    def action(value, max_requests=None):
        output = subprocess.run(
            loadtesting_command("job", str(root), value, max_requests=max_requests),
            shell=True,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(output.stdout)

    try:
        started = action("ensure")
        assert started["state"] == "running"
        poll_until(
            lambda: r if (r := action("status"))["state"] != "running" else None,
            timeout_s=20,
            interval_s=0.2,
        )
        result = action("status")
        assert result["state"] == "complete", result
        assert all(check["status"] == "passed" for check in result["checks"]), result
        assert action("ensure")["id"] == started["id"]
        assert list((tmp_path / "reports").glob("xwav-loadtesting-*"))
        assert not list((tmp_path / "reports").glob("xwav-preproduction-*"))
        from omnigent.diagnostics_runtime import collect
        from omnigent.penetration_runtime import inspect_reports
        from omnigent.preproduction_runtime import fingerprint, report_directory

        evidence = collect(
            "job", str(root), ["loadtesting"], report_directory, inspect_reports, fingerprint
        )["reports"][0]
        subprocess.run(evidence["rerun_command"], capture_output=True, text=True, check=True)
        verification = action("status")
        assert verification["checks"][0]["config"]["max_requests"] == 1000
        assert verification["checks"][0]["config"]["request_mode"] == "count"
        action("cancel")
        poll_until(lambda: action("status")["state"] != "running", timeout_s=10, interval_s=0.2)
        config(root, durations=dict.fromkeys(runtime.PROFILES, 10))
        new = action("start", max_requests=100_000_000)
        assert new["checks"][0]["config"]["max_requests"] == 100_000_000
        assert runtime.settings(root)["max_requests"] == 2000
        assert new["id"] != started["id"]
        action("cancel")
        poll_until(
            lambda: r if (r := action("status"))["state"] != "running" else None,
            timeout_s=10,
            interval_s=0.2,
        )
        result = action("status")
        assert result["state"] == "cancelled"
    finally:
        for record in Path("/tmp").glob("xwav-preview-*/*.json"):
            try:
                row = json.loads(record.read_text())
                process = psutil.Process(row["pid"])
                if (
                    process.cwd() == str(root)
                    and abs(process.create_time() - row["created"]) < 0.1
                ):
                    process.terminate()
                    process.wait(5)
            except (OSError, ValueError, psutil.Error):
                pass


@pytest.mark.parametrize("value", [0, -1, 100_000_001, True, 1.5, "100", None])
def test_request_override_validation(value):
    with pytest.raises(ValueError):
        runtime.validate_request_count(value)


def test_request_limit_boundaries_and_bounded_metric_storage(tmp_path):
    assert runtime.settings(tmp_path, 1)["max_requests"] == 1
    assert runtime.settings(tmp_path, 100_000_000)["max_requests"] == 100_000_000
    totals = runtime.SampleTotals()
    for index in range(20_000):
        totals.record(500 if index % 10 == 0 else 200, float(index % 100), 16, "")
    metrics = totals.metrics()
    assert metrics["requests"] == 20_000 and metrics["errors"] == 2000
    assert metrics["bytes_sampled"] == 320_000
    assert metrics["latency_sample_size"] == runtime.LATENCY_SAMPLES
    assert metrics["latency_percentiles_estimated"] is True
    assert 85 <= metrics["p95_ms"] <= 99
    assert sum(metrics["status_codes"].values()) == 20_000


@pytest.mark.parametrize("count", [1, 23, 1001])
def test_explicit_totals_send_exact_real_requests(service, tmp_path, count):
    port, agents = service
    config(tmp_path, requests_per_second=50)
    checks = runtime.discover(tmp_path, count)
    assert sum(check["target_requests"] for check in checks) == count
    budget = {"remaining": count, "sent": 0}
    actual = 0
    for check in checks:
        target = check["target_requests"]
        if not target:
            continue
        result = asyncio.run(
            runtime.measure(
                port,
                check["id"],
                check["config"],
                tmp_path / "cancel",
                lambda _: None,
                budget,
                target,
            )
        )
        assert result["status"] == "passed", result
        assert result["metrics"]["requests"] == target
        actual += result["metrics"]["requests"]
    assert actual == count == len(agents) == budget["sent"]
    assert budget["remaining"] == 0


def test_long_count_run_uses_live_heartbeat_not_duration_timeout(tmp_path, monkeypatch):
    import hashlib
    import os
    import time

    from omnigent import preproduction_runtime as coordinator

    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setenv("XWAV_TEST_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setattr(coordinator.os, "kill", lambda *_args: None)
    key = hashlib.sha256(f"job:{root}".encode()).hexdigest()
    directory = tmp_path / "reports" / f"xwav-loadtesting-{os.getuid()}" / key
    directory.mkdir(parents=True)
    report = {
        "id": "run",
        "state": "running",
        "started_at": time.time() - 100000,
        "heartbeat_at": time.time(),
        "worker_pid": 99999999,
        "checks": runtime.discover(root, 100_000_000),
    }
    coordinator.save(directory / "run.json", report)
    (directory / "latest").write_text("run")
    request = {"session_id": "job", "workspace": str(root), "action": "status"}
    current = coordinator.request_action(request, "", "", kind="loadtesting")
    assert current["state"] == "running"
    report["heartbeat_at"] = time.time() - 90
    coordinator.save(directory / "run.json", report)
    assert coordinator.request_action(request, "", "", kind="loadtesting")["state"] == "error"

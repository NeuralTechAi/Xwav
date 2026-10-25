"""Real bounded test processes, persistent reports and truthful coverage gaps."""

import json
import sys
from pathlib import Path

import pytest

from omnigent import preproduction_runtime as runtime
from omnigent.server.preproduction import preproduction_command
from tests._helpers.polling import poll_until


def configure(root, checks):
    (root / ".xwav").mkdir(exist_ok=True)
    (root / ".xwav" / "preproduction.json").write_text(json.dumps({"checks": checks}))


def test_discovers_existing_scripts_without_inventing_coverage(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "scripts": {
                    "test:unit": "vitest run",
                    "test:e2e": "playwright test",
                    "lint": "eslint .",
                }
            }
        )
    )
    checks = runtime.discover(tmp_path)
    assert next(c for c in checks if c["category"] == "unit")["command"] == [
        "npm",
        "run",
        "test:unit",
    ]
    assert next(c for c in checks if c["category"] == "integration")["status"] == "blocked"
    assert (
        next(c for c in checks if c["name"] == "Native iOS device tests")["status"]
        == "not_applicable"
    )
    assert all(c["status"] != "passed" for c in checks)


@pytest.mark.parametrize(
    "row",
    [
        {"category": "fake", "command": ["true"]},
        {"category": "unit", "command": "echo not argv"},
        {"category": "unit", "command": ["true"], "cwd": ".."},
        {"category": "unit", "command": ["true"], "timeout": 99999},
    ],
)
def test_invalid_configs_never_execute(tmp_path, row):
    configure(tmp_path, [row])
    with pytest.raises(ValueError):
        runtime.discover(tmp_path)


def test_runs_once_reuses_commands_and_records_failures(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    command = [
        sys.executable,
        "-c",
        """from pathlib import Path
p=Path('counter')
p.write_text(p.read_text()+'x' if p.exists() else 'x')
print('suite passed')""",
    ]
    configure(
        root,
        [{"category": c, "command": command} for c in ("unit", "regression")]
        + [
            {
                "category": "integration",
                "command": [
                    sys.executable,
                    "-c",
                    "print('failure evidence'); raise SystemExit(2)",
                ],
            }
        ],
    )
    report = {
        "id": "test",
        "state": "running",
        "workspace": str(root),
        "checks": runtime.discover(root),
        "source_version": runtime.fingerprint(root),
    }
    runtime.save(state / "test.json", report)
    runtime.worker(state, "test")
    result = json.loads((state / "test.json").read_text())
    assert result["state"] == "complete"
    assert (root / "counter").read_text() == "x"
    unit, regression, integration = result["checks"][:3]
    assert unit["status"] == regression["status"] == "passed"
    assert regression["reused"] is True
    assert integration["status"] == "failed" and integration["exit_code"] == 2
    assert "failure evidence" in integration["output"]
    assert result["source_changed"] is True


def test_timeouts_and_cancellation_are_not_passes(tmp_path):
    command = [sys.executable, "-c", "import time; time.sleep(30)"]
    cancelled = tmp_path / "cancel"
    timed = runtime.execute(command, tmp_path, 1, cancelled, tmp_path / "timeout.log")
    assert timed["status"] == "failed" and timed["reason"] == "Timeout"
    cancelled.touch()
    result = runtime.execute(command, tmp_path, 10, cancelled, tmp_path / "cancel.log")
    assert result["status"] == "cancelled"
    assert result["duration"] < 5


def test_missing_executable_and_secret_baseline(tmp_path):
    result = runtime.execute(
        ["xwav-nonexistent-check-tool"], tmp_path, 1, tmp_path / "cancel", tmp_path / "log"
    )
    assert result["status"] == "blocked"
    (tmp_path / "key.txt").write_text("-----BEGIN " + "PRIVATE KEY-----")
    finding = runtime.secret_scan(tmp_path)
    assert finding["status"] == "failed"
    assert "key.txt" in finding["output"]
    assert "PRIVATE KEY" not in finding["output"]


def test_transport_starts_persistent_worker_and_preserves_workspace(tmp_path, monkeypatch):
    import subprocess

    monkeypatch.setenv("XWAV_TEST_REPORT_ROOT", str(tmp_path / "reports"))
    root = tmp_path / "project with spaces"
    root.mkdir()
    configure(
        root,
        [{"category": "unit", "command": [sys.executable, "-c", "print('transport succeeded')"]}],
    )
    command = preproduction_command("job-one", str(root), "ensure")
    first = json.loads(
        subprocess.run(command, shell=True, capture_output=True, text=True, check=True).stdout
    )
    assert first["state"] == "running"

    def completed():
        response = subprocess.run(
            preproduction_command("job-one", str(root), "status"),
            shell=True,
            capture_output=True,
            text=True,
            check=True,
        )
        report = json.loads(response.stdout)
        return report if report["state"] != "running" else None

    poll_until(completed, timeout_s=15, interval_s=0.1)
    result = completed()
    assert result["id"] == first["id"]
    assert result["checks"][0]["status"] == "passed"
    again = json.loads(
        subprocess.run(command, shell=True, capture_output=True, text=True, check=True).stdout
    )
    assert again["id"] == first["id"]
    (root / "changed.txt").write_text("Source changed after the run")
    stale = json.loads(
        subprocess.run(command, shell=True, capture_output=True, text=True, check=True).stdout
    )
    assert stale["id"] == first["id"] and stale["source_changed"] is True


@pytest.mark.parametrize("platform", ["web", "android", "ios"])
def test_real_responsive_browser_baselines(tmp_path, monkeypatch, platform):
    import psutil

    from omnigent import preview_runtime

    storage = tmp_path / "runtime"
    storage.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    (project / "index.html").write_text(
        '<!doctype html><meta name="viewport" content="width=device-width">'
        "<title>Quality fixture</title><h1>App ready</h1>"
    )
    monkeypatch.chdir(project)
    monkeypatch.setattr(runtime, "QUALITY_ROOT", tmp_path / "quality-tools")
    monkeypatch.setattr(runtime.tempfile, "gettempdir", lambda: str(storage))
    try:
        result = runtime.browser_audit(project, platform, Path(preview_runtime.__file__))
        assert result["smoke"]["status"] == "passed"
        assert result["functional"]["status"] == "passed"
        assert result["usability"]["status"] == "passed"
        assert result["accessibility"]["status"] == "blocked"
        # Image-owned axe is usable without installing anything in the project.
        axe = runtime.QUALITY_ROOT / "node_modules/axe-core/axe.min.js"
        axe.parent.mkdir(parents=True)
        axe.write_text("window.axe = {run: async () => ({violations: [], incomplete: []})};")
        bundled = runtime.browser_audit(project, platform, Path(preview_runtime.__file__))
        assert bundled["accessibility"]["status"] == "passed"
        axe.write_text(
            'window.axe = {run: async () => ({violations: [{id: "contrast", '
            'impact: "serious", description: "Low contrast", nodes: [1]}], incomplete: []})};'
        )
        violation = runtime.browser_audit(project, platform, Path(preview_runtime.__file__))
        assert violation["accessibility"]["status"] == "failed"
        assert "contrast" in violation["accessibility"]["output"]
        (project / "index.html").write_text(
            '<meta name="viewport" content="width=device-width">'
            '<div style="width:2500px">Overflow</div>'
            '<script>throw Error("broken app")</script>'
        )
        failed = runtime.browser_audit(project, platform, Path(preview_runtime.__file__))
        assert failed["functional"]["status"] == "failed"
        assert failed["usability"]["status"] == "failed"
    finally:
        for record in storage.rglob("*.json"):
            data = json.loads(record.read_text())
            try:
                process = psutil.Process(data["pid"])
                if abs(process.create_time() - data["created"]) < 0.1:
                    process.terminate()
                    process.wait(5)
            except psutil.NoSuchProcess:
                pass


def test_native_node_checks_execute_and_keep_missing_flows_visible(tmp_path):
    import shutil

    if not shutil.which("node") or not shutil.which("npm"):
        pytest.skip("Node tooling required")
    (tmp_path / "package.json").write_text('{"name":"fixture","version":"1.0.0"}')
    (tmp_path / "package-lock.json").write_text(
        '{"name":"fixture","version":"1.0.0","lockfileVersion":3,"packages":{}}'
    )
    source = tmp_path / "app.js"
    source.write_text("const broken = ;")
    checks = runtime.discover(tmp_path)
    syntax = next(c for c in checks if c["category"] == "static")
    failed = runtime.execute(
        syntax["command"], tmp_path, 10, tmp_path / "cancel", tmp_path / "syntax.log"
    )
    assert failed["status"] == "failed" and "SyntaxError" in failed["output"]
    source.write_text("const ready = true;")
    passed = runtime.execute(
        syntax["command"], tmp_path, 10, tmp_path / "cancel", tmp_path / "syntax.log"
    )
    assert passed["status"] == "passed"
    assert any(c["command"] == ["npm", "audit", "--audit-level=moderate"] for c in checks)
    assert next(c for c in checks if c["category"] == "integration")["status"] == "blocked"
    configure(tmp_path, [{"category": "unit", "command": ["node", "--version"]}])
    explicit = runtime.discover(tmp_path)
    assert not any(c["name"].startswith("JavaScript syntax") for c in explicit)

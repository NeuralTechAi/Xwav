"""Dashboard evidence reaches harnesses without assuming project-owned test files."""

import json
import subprocess
import sys

import httpx
import pytest

from omnigent import diagnostics_runtime as runtime
from omnigent.preproduction_runtime import fingerprint, report_directory
from omnigent.server.diagnostics import (
    collect_diagnostics,
    diagnostics_command,
    evidence_text,
    requested_kinds,
    requested_run,
)


@pytest.mark.parametrize(
    "kind,text",
    [
        ("preproduction", "check the Pre-Production Tests, identify the issues and fix them all"),
        ("loadtesting", "Fix the load testing errors"),
        ("penetration", "Fix the Strix findings"),
        ("releases", "Fix compilation and deployment issues"),
    ],
)
def test_report_requests_select_only_relevant_evidence(kind, text):
    assert requested_kinds([{"type": "input_text", "text": text}]) == [kind]
    assert requested_kinds([{"type": "input_text", "text": "Change the title color"}]) == []
    run = "a" * 32
    assert requested_run([{"text": f"Fix Penetration Test (run {run})"}], ["penetration"]) == run
    assert requested_run([{"text": f"Fix build (run {run})"}], ["releases"]) is None


@pytest.mark.parametrize("kind", ["preproduction", "loadtesting", "releases"])
def test_transported_reader_preserves_failures_isolation_and_secret_redaction(
    tmp_path, monkeypatch, kind
):
    monkeypatch.setenv("XWAV_TEST_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("SAMPLE_API_KEY", "private-test-secret")
    root = tmp_path / "app"
    root.mkdir()
    (root / "index.html").write_text("app")
    directory = report_directory(root, "job-one", kind)
    directory.mkdir(parents=True)
    run_id = "a" * 32
    (directory / "latest").write_text(run_id)
    report = {
        "id": run_id,
        "session_id": "job-one",
        "workspace": str(root),
        "state": "complete",
        "source_version": fingerprint(root),
        "checks": [
            {
                "name": "Real failure",
                "status": "failed",
                "command": ["python", "check.py"],
                "output": "Expected 5, got 4. private-test-secret",
                "metrics": {"p95_ms": 1800},
            }
        ],
    }
    path = directory / f"{run_id}.json"
    path.write_text(json.dumps(report))
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            diagnostics_command("job-one", str(root), [kind])
            .split("\n", 1)[1]
            .rsplit("XWAV_DIAGNOSTICS", 1)[0],
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(process.stdout)
    evidence = payload["reports"][0]
    assert evidence["counts"]["failed"] == 1
    assert evidence["checks"][0]["command"] == ["python", "check.py"]
    assert "Expected 5, got 4" in evidence["checks"][0]["output"]
    assert "private-test-secret" not in process.stdout
    assert "[redacted]" in process.stdout
    assert "rerun_command" in evidence if kind != "releases" else True
    assert requested_kinds([{"text": "ordinary chat"}]) == []
    # A workspace must never attach another session's cached report.
    report["session_id"] = "another-job"
    path.write_text(json.dumps(report))
    result = runtime.collect(
        "job-one", str(root), [kind], report_directory, lambda _: {}, fingerprint
    )
    assert result["reports"][0]["state"] == "unavailable"


def test_stale_missing_and_oversized_reports_are_not_passes(tmp_path):
    result = runtime.collect(
        "job", str(tmp_path), ["preproduction"], report_directory, lambda _: {}, fingerprint
    )
    assert result["reports"][0]["state"] == "empty"
    path = tmp_path / "oversized.json"
    path.write_text("x" * 100)
    with pytest.raises(ValueError):
        runtime.read_report(path, limit=20)
    link = tmp_path / "linked.json"
    link.symlink_to(path)
    with pytest.raises(OSError):
        runtime.read_report(link)
    assert len(evidence_text({"output": "x" * 100000})) < 32000
    assert "untrusted evidence" in evidence_text({})


@pytest.mark.asyncio
@pytest.mark.parametrize("run_id", [None, "a" * 32])
async def test_managed_strix_findings_and_infrastructure_errors_are_included(monkeypatch, run_id):
    from omnigent.server import strix_jobs

    monkeypatch.setattr(
        strix_jobs,
        "report",
        lambda _, selected=None: {
            "state": "error",
            "error": "Docker unavailable",
            "run": {"id": selected or "scan-one"},
            "findings": [{"title": "Injection", "severity": "high", "evidence": "file.py:10"}],
        },
    )

    def upstream(request):
        return httpx.Response(
            200,
            json={
                "exit_code": 0,
                "stdout": json.dumps(
                    {
                        "session_id": "job",
                        "reports": [{"kind": "penetration", "state": "empty"}],
                    }
                ),
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(upstream), base_url="http://runner"
    ) as client:
        result = await collect_diagnostics(client, "job", "/workspace", ["penetration"], run_id)
    assert result["reports"][0]["error"] == "Docker unavailable"
    assert result["reports"][0]["run"]["id"] == (run_id or "scan-one")
    assert result["reports"][0]["findings"][0]["evidence"] == "file.py:10"

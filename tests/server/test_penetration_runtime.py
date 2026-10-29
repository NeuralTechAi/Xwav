"""Strix reports are read-only, bounded and isolated to the selected workspace."""

import json
import os
import subprocess

import pytest

from omnigent.penetration_runtime import inspect_reports
from omnigent.server.penetration import penetration_command


def write_run(root, name="scan-one", **record):
    run = root / "strix_runs" / name
    run.mkdir(parents=True)
    (run / "run.json").write_text(json.dumps({"status": "completed", **record}))
    return run


def test_current_strix_findings_counts_evidence_and_summary(tmp_path):
    run = write_run(
        tmp_path, scan_results={"executive_summary": "Review summary"}, scan_mode="quick"
    )
    (run / "vulnerabilities.json").write_text(
        json.dumps(
            [
                {
                    "id": "vuln-1",
                    "title": "Access control",
                    "severity": "HIGH",
                    "evidence": "GET /private",
                    "remediation_steps": "Check ownership",
                    "verified": True,
                },
                {"id": "vuln-2", "title": "Headers", "severity": "informational"},
                {"id": "vuln-3", "title": "Unclassified", "severity": "unexpected"},
            ]
        )
    )
    report = inspect_reports(str(tmp_path))
    assert report["state"] == "complete"
    assert report["counts"]["high"] == report["counts"]["info"] == report["counts"]["unknown"] == 1
    assert report["run"]["summary"] == "Review summary"
    assert report["findings"][0]["evidence"] == "GET /private"
    assert report["findings"][0]["validation"] == "verified"
    assert report["findings"][1]["validation"] == "reported"


def test_empty_incomplete_legacy_and_selected_history(tmp_path):
    assert inspect_reports(str(tmp_path))["state"] == "empty"
    first = write_run(tmp_path, status="running")
    report = inspect_reports(str(tmp_path))
    assert report["state"] == "running" and report["warnings"]
    (first / "run.json").unlink()
    (first / "scan_data.json").write_text(
        json.dumps(
            {
                "scan_results": {"scan_completed": True},
                "vulnerability_reports": [{"title": "Legacy finding", "severity": "low"}],
            }
        )
    )
    write_run(tmp_path, "scan-two", status="interrupted")
    assert inspect_reports(str(tmp_path), "scan-two")["state"] == "stopped"
    report = inspect_reports(str(tmp_path), "scan-one")
    assert len(report["runs"]) == 2 and report["state"] == "complete"
    assert report["findings"][0]["title"] == "Legacy finding"
    assert inspect_reports(str(tmp_path), "scan-one") == report


@pytest.mark.parametrize("run_id", ["../other", "a/b", "..", "", "a\\b", "\x00"])
def test_refuses_path_traversal(tmp_path, run_id):
    with pytest.raises(ValueError):
        inspect_reports(str(tmp_path), run_id)


def test_symlink_escape_and_special_files_are_never_read(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "strix_runs").symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        inspect_reports(str(root))
    (root / "strix_runs").unlink()
    run = write_run(root)
    (run / "vulnerabilities.json").symlink_to(outside / "secret")
    with pytest.raises(OSError):
        inspect_reports(str(root))
    (run / "vulnerabilities.json").unlink()
    os.mkfifo(run / "vulnerabilities.json")
    with pytest.raises(ValueError, match="regular files"):
        inspect_reports(str(root))


def test_malformed_oversized_and_truncated_reports_are_explicit(tmp_path):
    run = write_run(tmp_path)
    (run / "vulnerabilities.json").write_text("bad json")
    with pytest.raises(ValueError):
        inspect_reports(str(tmp_path))
    (run / "vulnerabilities.json").write_text("x" * (2 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match="size limit"):
        inspect_reports(str(tmp_path))
    (run / "vulnerabilities.json").write_text(
        json.dumps([{"title": str(i), "severity": "low"} for i in range(205)])
    )
    report = inspect_reports(str(tmp_path))
    assert len(report["findings"]) == 200 and report["counts"]["low"] == 205
    assert report["total_findings"] == 205 and report["warnings"]


def test_transport_quotes_workspace_and_never_starts_scans(tmp_path):
    root = tmp_path / "project'$(touch injected)"
    root.mkdir()
    write_run(root)
    command = penetration_command(str(root), "scan-one")
    result = subprocess.run(
        command, shell=True, text=True, capture_output=True, check=True, cwd=tmp_path
    )
    assert json.loads(result.stdout)["state"] == "complete"
    assert not (tmp_path / "injected").exists()
    assert list(root.iterdir()) == [root / "strix_runs"]

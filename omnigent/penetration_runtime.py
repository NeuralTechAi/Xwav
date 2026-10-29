"""Read bounded Strix artifacts from this workspace without running scan code."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

SEVERITIES = ("critical", "high", "medium", "low", "info", "unknown")
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
NOTICE = (
    "Results reported by Strix for this workspace. "
    "Missing or incomplete reports are not a security pass."
)


def _read(directory: int, name: str, limit: int) -> object | None:
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    except FileNotFoundError:
        return None
    try:
        import stat

        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("Report artifacts must be regular files")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            content = stream.read(limit + 1)
        if len(content) > limit:
            raise ValueError("Strix report exceeds the dashboard size limit")
        return json.loads(content)
    finally:
        os.close(descriptor)


def _text(value: object, limit: int = 10000) -> str:
    return value[:limit] if isinstance(value, str) else ""


def inspect_reports(workspace: str | None = None, run_id: str | None = None) -> dict:
    root = Path(workspace or Path.cwd()).expanduser().resolve()
    report: dict = {
        "state": "empty",
        "runs": [],
        "findings": [],
        "warnings": [],
        "counts": dict.fromkeys(SEVERITIES, 0),
        "notice": NOTICE,
        "strix_installed": shutil.which("strix") is not None,
    }
    if run_id is not None and (
        not isinstance(run_id, str)
        or not run_id
        or len(run_id) > 200
        or run_id in {".", ".."}
        or any(c in run_id for c in "/\\\x00")
    ):
        raise ValueError("Invalid Strix run identifier")
    try:
        directory = os.open(root / "strix_runs", DIRECTORY_FLAGS)
    except FileNotFoundError:
        return report
    try:
        runs: list[dict[str, Any]] = []
        with os.scandir(directory) as entries:
            for index, entry in enumerate(entries):
                if index >= 500:
                    report["warnings"].append("Only the first 500 report folders were inspected.")
                    break
                if entry.is_dir(follow_symlinks=False):
                    runs.append(
                        {
                            "id": entry.name,
                            "updated_at": entry.stat(follow_symlinks=False).st_mtime,
                        }
                    )
        runs.sort(key=lambda row: (row["updated_at"], row["id"]), reverse=True)
        report["runs"] = runs[:100]
        if len(runs) > 100:
            report["warnings"].append("Showing the 100 most recently updated scan folders.")
        selected = run_id or (runs[0]["id"] if runs else None)
        if selected is None:
            return report
        if selected not in {row["id"] for row in runs}:
            raise ValueError("Strix run not found in this workspace")
        child = os.open(selected, DIRECTORY_FLAGS, dir_fd=directory)
        try:
            record = _read(child, "run.json", 1024 * 1024)
            if record is None:
                record = _read(child, "scan_data.json", 1024 * 1024)
            if record is not None and not isinstance(record, dict):
                raise ValueError("Invalid Strix run metadata")
            record = record or {}
            findings = _read(child, "vulnerabilities.json", 2 * 1024 * 1024)
            if findings is None:
                findings = record.get("vulnerability_reports")
            if findings is None:
                report["warnings"].append("No findings index has been written for this scan yet.")
                findings = []
            if not isinstance(findings, list) or any(
                not isinstance(row, dict) for row in findings
            ):
                raise ValueError("Invalid Strix findings index")
            results = record.get("scan_results")
            results = results if isinstance(results, dict) else {}
            status = _text(record.get("status"), 50)
            state = {
                "completed": "complete",
                "complete": "complete",
                "running": "running",
                "failed": "error",
                "error": "error",
                "interrupted": "stopped",
                "stopped": "stopped",
                "cancelled": "stopped",
            }.get(status, "unknown")
            if state == "unknown" and results.get("scan_completed") is True:
                state = "complete"
            if not record:
                report["warnings"].append(
                    "Scan state is unavailable; these findings do not establish a completed scan."
                )
            report.update(
                state=state,
                run={
                    "id": selected,
                    "state": state,
                    "started_at": _text(record.get("start_time"), 100),
                    "finished_at": _text(record.get("end_time"), 100),
                    "mode": _text(record.get("scan_mode"), 50),
                    "summary": _text(
                        results.get("executive_summary") or record.get("final_scan_result"), 20000
                    ),
                    "recommendations": _text(results.get("recommendations"), 20000),
                },
            )
            for index, finding in enumerate(findings):
                severity = _text(finding.get("severity"), 30).lower()
                if severity == "informational":
                    severity = "info"
                if severity not in SEVERITIES:
                    severity = "unknown"
                report["counts"][severity] += 1
                if index < 200:
                    report["findings"].append(
                        {
                            "id": _text(finding.get("id"), 200) or f"finding-{index + 1}",
                            "title": _text(finding.get("title"), 500) or "Untitled finding",
                            "severity": severity,
                            "validation": "verified"
                            if finding.get("verified") is True
                            or finding.get("status") == "verified"
                            else "reported",
                            **{
                                field: _text(finding.get(field))
                                for field in (
                                    "description",
                                    "impact",
                                    "target",
                                    "evidence",
                                    "technical_analysis",
                                    "poc_description",
                                    "remediation_steps",
                                )
                            },
                        }
                    )
            report["total_findings"] = len(findings)
            report["findings"].sort(key=lambda row: SEVERITIES.index(row["severity"]))
            if len(findings) > 200:
                report["warnings"].append(
                    "Showing the first 200 findings; severity totals include the whole index."
                )
            return report
        finally:
            os.close(child)
    finally:
        os.close(directory)

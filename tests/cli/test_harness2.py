"""Harness² forwards explicit workflows without altering chat executor configuration."""

from __future__ import annotations

import json
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from omnigent import cli_harness2


@pytest.fixture
def pinned_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    distribution = Mock(version="0.1.0")
    distribution.read_text.return_value = json.dumps(
        {"vcs_info": {"commit_id": cli_harness2.HARNESS2_REVISION}}
    )
    monkeypatch.setattr(metadata, "distribution", lambda name: distribution)


def test_status_missing_is_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(name: str):
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(metadata, "distribution", missing)
    run = Mock(side_effect=AssertionError("Status must not execute any process"))
    monkeypatch.setattr(subprocess, "run", run)
    result = CliRunner().invoke(cli_harness2.harness2, ["status", "--json"])
    assert result.exit_code == 0, result.output
    state = json.loads(result.output)
    assert state["installed"] is False
    assert state["pinned"] is False
    assert state["interactive_chat"] is False
    run.assert_not_called()


@pytest.mark.parametrize("metadata_text", [None, "not-json", "[]", '{"vcs_info":[]}'])
def test_unverified_runtime_is_not_executed(metadata_text, monkeypatch):
    distribution = Mock(version="0.1.0")
    distribution.read_text.return_value = metadata_text
    monkeypatch.setattr(metadata, "distribution", lambda name: distribution)
    run = Mock(side_effect=AssertionError("Unverified upstream version must not execute"))
    monkeypatch.setattr(subprocess, "run", run)
    result = CliRunner().invoke(cli_harness2.harness2, ["demo"])
    assert result.exit_code == 1, result.output
    assert cli_harness2.HARNESS2_REVISION in result.output
    assert "Install it" in result.output
    run.assert_not_called()


@pytest.mark.parametrize(
    ("command", "module"),
    [
        ("demo", "demo"),
        ("run", "run_sweep"),
        ("check", "check"),
        ("judge", "judge"),
        ("report", "report"),
    ],
)
def test_explicit_commands_preserve_arguments(command, module, pinned_runtime, monkeypatch):
    run = Mock(return_value=subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(subprocess, "run", run)
    arguments = ["--output", "a path with spaces; $(literal)", "--k", "2", "--mode", "both"]
    result = CliRunner().invoke(cli_harness2.harness2, [command, *arguments])
    assert result.exit_code == 0, result.output
    run.assert_called_once_with(
        [sys.executable, "-m", f"harness2.cli.{module}", *arguments], check=False
    )


@pytest.mark.parametrize(("returncode", "expected"), [(2, 2), (7, 7), (-15, 143)])
def test_upstream_failure_exit_status(pinned_runtime, monkeypatch, returncode, expected):
    monkeypatch.setattr(
        subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], returncode))
    )
    result = CliRunner().invoke(cli_harness2.harness2, ["check", "--bench", "lab"])
    assert result.exit_code == expected


def test_upstream_help_is_forwarded(pinned_runtime, monkeypatch):
    run = Mock(return_value=subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(subprocess, "run", run)
    result = CliRunner().invoke(cli_harness2.harness2, ["run", "--help"])
    assert result.exit_code == 0
    assert run.call_args.args[0][-1] == "--help"


def test_process_failure_is_actionable(pinned_runtime, monkeypatch):
    monkeypatch.setattr(subprocess, "run", Mock(side_effect=OSError("executor unavailable")))
    result = CliRunner().invoke(cli_harness2.harness2, ["demo"])
    assert result.exit_code == 1
    assert "Could not start Harness²: executor unavailable" in result.output


def test_no_default_benchmark_run(pinned_runtime, monkeypatch):
    run = Mock(side_effect=AssertionError("Group help must not start an experiment"))
    monkeypatch.setattr(subprocess, "run", run)
    result = CliRunner().invoke(cli_harness2.harness2, ["--help"])
    assert result.exit_code == 0
    assert "separate from chat" in result.output
    run.assert_not_called()


def test_real_demo_without_credentials(tmp_path: Path):
    if not cli_harness2.installation_status()["pinned"]:
        pytest.skip("Optional reviewed Harness² runtime is not installed")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "omnigent",
            "harness2",
            "demo",
            "--output",
            str(tmp_path / "demo"),
            "--k",
            "2",
            "--mode",
            "both",
        ],
        env={
            "PATH": str(Path(sys.executable).parent),
            "HOME": str(tmp_path / "home"),
            "PYTHONNOUSERSITE": "1",
        },
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((tmp_path / "demo" / "demo.json").read_text())
    assert report["done"] == 2
    assert report["failed"] == 0
    assert report["execution_count"] > 0
    assert report["editor_calls"] > 0
    # Real engine outcomes include both recursion modes, not just CLI return success.
    summaries = list((tmp_path / "demo").rglob("summary.json"))
    assert summaries
    modes = set()
    for path in summaries:
        summary = json.loads(path.read_text())
        modes.update(summary.get("modes", {}))
    assert {"agg", "seq"} <= modes

"""Shared SoL-Pi calls use Xwav, remain explicit and preserve project settings."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from click.testing import CliRunner

from omnigent import cli_sol_pi
from omnigent.harness_plugins import valid_harnesses
from omnigent.inner.pi_executor import _resolve_pi_bundle_extension_args
from omnigent.spec.parser import parse
from omnigent.spec.validator import validate


def test_status_is_offline_and_does_not_start_or_install(monkeypatch):
    run = Mock(side_effect=AssertionError("Status cannot start processes"))
    monkeypatch.setattr(subprocess, "run", run)
    result = CliRunner().invoke(cli_sol_pi.sol_pi, ["status", "--json"])
    assert result.exit_code == 0, result.output
    state = json.loads(result.output)
    assert state["revision"] == "219568034fa54ed121ede80961655e33dfb9d0e3"
    assert state["verified"] is True
    assert 100_000 < state["bundled_bytes"] < 150_000
    assert state["profile"] == {
        "actionFusion": False,
        "observationPack": True,
        "evidencePreservingReducer": False,
        "onlineContextCompact": False,
    }
    assert state["automatic_install"] is state["extra_model_calls"] is False
    run.assert_not_called()


def test_exported_worker_uses_existing_executor_and_selected_workspace(tmp_path):
    workspace = tmp_path / "project with spaces"
    workspace.mkdir()
    existing = workspace / ".pi/settings.json"
    existing.parent.mkdir()
    existing.write_text('{"defaultProvider":"user-choice"}')
    destination = tmp_path / "parent/agents/sol-pi"
    result = CliRunner().invoke(
        cli_sol_pi.sol_pi,
        [
            "export-agent",
            str(destination),
            "--project",
            str(workspace),
            "--timeout",
            "120",
            "--max-iterations",
            "4",
        ],
    )
    assert result.exit_code == 0, result.output
    spec = parse(destination)
    assert validate(spec).valid
    assert spec.executor.harness_kind == "pi"
    assert spec.executor.timeout == 120
    assert spec.executor.max_iterations == 4
    assert spec.skills_filter == "none"
    assert spec.os_env.cwd == str(workspace)
    args = _resolve_pi_bundle_extension_args(destination)
    assert args == ["--extension", str(destination / ".pi/extensions/sol-pi/index.ts")]
    from omnigent.cli import _bundle

    with tarfile.open(fileobj=io.BytesIO(_bundle(destination)), mode="r:gz") as archive:
        assert ".pi/extensions/sol-pi/runtime/index.ts" in archive.getnames()
        assert "config.yaml" in archive.getnames()
    assert existing.read_text() == '{"defaultProvider":"user-choice"}'
    assert not (workspace / ".pi/sol-pi.json").exists()
    again = CliRunner().invoke(cli_sol_pi.sol_pi, ["export-agent", str(destination)])
    assert again.exit_code == 1
    assert "already exists" in again.output


@pytest.mark.parametrize("harness", sorted(valid_harnesses()))
def test_registered_parent_harnesses_can_attach_the_worker(tmp_path, harness):
    parent = tmp_path / "parent"
    cli_sol_pi.export_worker(parent / "agents/sol-pi", tmp_path, 120, 4)
    (parent / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "spec_version": 1,
                "name": "parent",
                "executor": {"type": "omnigent", "config": {"harness": harness}},
                "tools": {"agents": ["sol-pi"]},
            }
        )
    )
    spec = parse(parent)
    assert spec.executor.harness_kind == harness
    assert spec.tools.agents == ["sol-pi"]
    assert len(spec.sub_agents) == 1
    assert spec.sub_agents[0].executor.harness_kind == "pi"


@pytest.mark.parametrize("code", [0, 2, -15])
def test_any_caller_runs_the_same_bounded_worker_without_copying_credentials(
    tmp_path, monkeypatch, code
):
    task = tmp_path / "task.md"
    task.write_text("Inspect this project; do not edit. Literal $(never-execute).")
    bundles = []

    def dispatch(args, *, cwd, env, check):
        assert args[1:4] == ["-m", "omnigent.cli", "run"]
        bundle = Path(args[4])
        bundles.append(bundle)
        assert parse(bundle).executor.harness_kind == "pi"
        assert args[5:11] == ["--server", "", "--tools", "coding", "--prompt", task.read_text()]
        assert args[11:] == ["--model", "configured/provider-model"]
        assert cwd == tmp_path and check is False
        assert env["XWAV_SOL_PI_WORKER"] == "1"
        assert not list(bundle.rglob("auth.json"))
        return subprocess.CompletedProcess(args, code)

    monkeypatch.setattr(subprocess, "run", dispatch)
    result = CliRunner().invoke(
        cli_sol_pi.sol_pi,
        [
            "run",
            "--task-file",
            str(task),
            "--project",
            str(tmp_path),
            "--model",
            "configured/provider-model",
        ],
    )
    assert result.exit_code == (code if code >= 0 else 128 - code), result.output
    assert bundles and not bundles[0].exists()


@pytest.mark.parametrize("content", [" ", "x" * 65537], ids=["blank", "oversized"])
def test_invalid_task_never_starts_a_worker(tmp_path, monkeypatch, content):
    task = tmp_path / "task.md"
    task.write_text(content)
    run = Mock(side_effect=AssertionError("Invalid task must not start"))
    monkeypatch.setattr(subprocess, "run", run)
    result = CliRunner().invoke(cli_sol_pi.sol_pi, ["run", "--task-file", str(task)])
    assert result.exit_code == 1 and "64 KiB" in result.output
    run.assert_not_called()


def test_nested_worker_is_rejected_before_reading_task(tmp_path, monkeypatch):
    task = tmp_path / "task.md"
    task.write_text("Task")
    monkeypatch.setenv("XWAV_SOL_PI_WORKER", "1")
    result = CliRunner().invoke(cli_sol_pi.sol_pi, ["run", "--task-file", str(task)])
    assert result.exit_code == 1 and "Nested" in result.output


def test_unverified_resources_cannot_be_exported(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_sol_pi, "resource_status", lambda: {"verified": False})
    destination = tmp_path / "agent"
    result = CliRunner().invoke(cli_sol_pi.sol_pi, ["export-agent", str(destination)])
    assert result.exit_code == 1 and "integrity" in result.output
    assert not destination.exists()


def test_sol_pi_is_registered_without_changing_default_harness():
    from omnigent.cli import cli

    result = CliRunner().invoke(cli, ["sol-pi", "--help"], prog_name="xwav")
    assert result.exit_code == 0, result.output
    assert "export-agent" in result.output


def test_real_pi_loads_worker_and_preserves_packed_evidence(tmp_path):
    root = Path(__file__).parents[2]
    pi_root = root / ".omnigent/harness-tools/node_modules/@earendil-works/pi-coding-agent"
    if not (pi_root / "dist/index.js").is_file() or not shutil.which("node"):
        pytest.skip("The optional local Pi acceptance runtime is not installed")
    bundle = tmp_path / "agent"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    cli_sol_pi.export_worker(bundle, workspace, 120, 6)
    result = subprocess.run(
        [
            "node",
            str(Path(__file__).with_name("sol_pi_probe.mjs")),
            str(pi_root),
            str(bundle),
            str(workspace),
        ],
        env={
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(tmp_path),
            "PI_CODING_AGENT_DIR": str(tmp_path / "private-pi"),
        },
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["exact_recall"] is True

"""On-demand SoL-Pi workers callable from any Xwav harness."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import click
import yaml

from omnigent.native_skills import native_skill_root

_WORKER_ENV = "XWAV_SOL_PI_WORKER"
_PROFILE = {
    "actionFusion": False,
    "observationPack": True,
    "evidencePreservingReducer": False,
    "onlineContextCompact": False,
}
_ENTRY = """import { registerConfiguredFeatures } from './runtime/index.ts';
import { DEFAULT_CONFIG } from './runtime/config.ts';

export default function (pi) {
  let initialized = false;
  pi.on('session_start', () => {
    if (initialized) return;
    initialized = true;
    // Respect an existing provider of the same recall tool.
    if (pi.getAllTools().some(tool => tool.name === 'obs_recall')) return;
    registerConfiguredFeatures(pi, {
      ...DEFAULT_CONFIG,
      ...__XWAV_PROFILE__,
    });
  });
}
"""


def resource_status() -> dict[str, object]:
    """Inspect pinned resources offline without starting Pi or reading credentials."""
    root = native_skill_root() / "sol-pi"
    manifest = json.loads((root / "upstream.json").read_text())
    files = manifest["files"]
    verified = all(
        (root / name).is_file()
        and not (root / name).is_symlink()
        and hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
        for name, digest in files.items()
    )
    return {
        "source": manifest["repository"],
        "revision": manifest["revision"],
        "version": manifest["version"],
        "verified": verified,
        "bundled_bytes": sum(
            (root / name).stat().st_size for name in files if (root / name).is_file()
        ),
        "profile": dict(_PROFILE),
        "caller_harness": "any harness with shell access or Xwav sub-agent tools",
        "worker_harness": "pi",
        "pi_on_path": shutil.which("pi") is not None,
        "extra_model_calls": False,
        "automatic_install": False,
    }


def export_worker(destination: Path, workspace: Path, timeout: int, max_iterations: int) -> None:
    """Create a portable agent without replacing an existing directory or settings."""
    if not resource_status()["verified"]:
        raise click.ClickException(
            "Bundled SoL-Pi resources failed integrity checks. Reinstall Xwav."
        )
    if destination.exists() or destination.is_symlink():
        raise click.ClickException(
            f"Destination already exists: {destination}. Choose a new directory."
        )
    destination.mkdir(parents=True)
    extension = destination / ".pi/extensions/sol-pi"
    extension.mkdir(parents=True)
    root = native_skill_root() / "sol-pi"
    try:
        shutil.copytree(root / "runtime", extension / "runtime")
        for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "upstream.json"):
            shutil.copyfile(root / name, extension / name)
        (extension / "index.ts").write_text(
            _ENTRY.replace("__XWAV_PROFILE__", json.dumps(_PROFILE))
        )
        config = {
            "spec_version": 1,
            "name": "sol-pi",
            "description": "On-demand SoL-Pi observation-efficient worker for any parent harness.",
            "executor": {
                "type": "omnigent",
                "config": {"harness": "pi"},
                "timeout": timeout,
                "max_iterations": max_iterations,
            },
            "skills": "none",
            "prompt": (
                "Complete only the supplied task in the selected workspace. "
                "Use the normal Xwav tools and approval path. Retain exact evidence with "
                "obs_recall when an observation is packed. Report changed files, checks, "
                "and unresolved issues. Do not launch more workers or copy credentials."
            ),
            "os_env": {"type": "caller_process", "cwd": str(workspace)},
        }
        (destination / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    except BaseException:
        shutil.rmtree(destination)
        raise


@click.group("sol-pi")
def sol_pi() -> None:
    """Use a lightweight SoL-Pi worker from any harness; nothing starts implicitly."""


@sol_pi.command("status")
@click.option("--json", "as_json", is_flag=True)
def status(as_json: bool) -> None:
    """Check bundled resources without network access, setup changes or model calls."""
    state = resource_status()
    if as_json:
        click.echo(json.dumps(state, indent=2))
    else:
        click.echo(f"SoL-Pi {state['version']}, revision {state['revision']}")
        click.echo(
            f"Resources verified: {state['verified']}; source bytes: {state['bundled_bytes']}"
        )
        click.echo("Any caller harness; optional Pi worker. Only ObservationPack is enabled.")
        click.echo("Run requires Node >=22.19, a compatible Pi and a configured model account.")
    if not state["verified"]:
        raise click.exceptions.Exit(1)


def _worker_options(command):
    command = click.option(
        "--project", type=click.Path(exists=True, file_okay=False, path_type=Path), default="."
    )(command)
    command = click.option("--timeout", type=click.IntRange(1, 7200), default=600)(command)
    return click.option("--max-iterations", type=click.IntRange(1, 200), default=20)(command)


@sol_pi.command("export-agent")
@click.argument("destination", type=click.Path(path_type=Path))
@_worker_options
def export_agent(destination: Path, project: Path, timeout: int, max_iterations: int) -> None:
    """Export an agent for shared sub-agent tools or Settings import; no Pi run."""
    export_worker(destination.absolute(), project.resolve(), timeout, max_iterations)
    click.echo(f"Exported SoL-Pi worker to {destination.absolute()}")
    click.echo("Attach it as agents/sol-pi in any parent agent, or import its bundle in Settings.")


@sol_pi.command("run")
@click.option(
    "--task-file", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option("--model", default=None, help="Use a model configured in this job's Pi account.")
@_worker_options
def run_worker(
    task_file: Path, model: str | None, project: Path, timeout: int, max_iterations: int
) -> None:
    """Run an explicit task through Xwav's normal Pi executor, not raw Pi."""
    if os.environ.get(_WORKER_ENV):
        raise click.ClickException("Nested SoL-Pi workers are disabled.")
    try:
        with task_file.open("rb") as stream:
            raw_task = stream.read(65537)
        task = raw_task.decode("utf-8")
    except (OSError, UnicodeError) as error:
        raise click.ClickException(f"Cannot read the UTF-8 task file: {error}") from error
    if not task.strip() or len(raw_task) > 65536:
        raise click.ClickException("Supply a nonempty task file of at most 64 KiB.")
    project = project.resolve()
    with tempfile.TemporaryDirectory(prefix="xwav-sol-pi-") as temporary:
        bundle = Path(temporary) / "agent"
        export_worker(bundle, project, timeout, max_iterations)
        args = [
            sys.executable,
            "-m",
            "omnigent.cli",
            "run",
            str(bundle),
            "--server",
            "",
            "--tools",
            "coding",
            "--prompt",
            task,
        ]
        if model:
            args.extend(["--model", model])
        click.echo(
            "Starting a scoped SoL-Pi worker. The main model may incur normal usage charges.",
            err=True,
        )
        try:
            result = subprocess.run(
                args, cwd=project, env={**os.environ, _WORKER_ENV: "1"}, check=False
            )
        except OSError as error:
            raise click.ClickException(f"Could not start the Xwav worker: {error}") from error
        if result.returncode:
            raise click.exceptions.Exit(
                result.returncode if result.returncode > 0 else 128 - result.returncode
            )

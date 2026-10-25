"""Optional Harness² benchmark workflow, separate from interactive chat executors."""

from __future__ import annotations

import json
import subprocess
import sys
from importlib import metadata

import click

HARNESS2_REVISION = "1cfe254e8d25b15f37048c3730134686abe60335"
HARNESS2_SOURCE = "https://github.com/google-research/harness2"
HARNESS2_REQUIREMENT = f"harness2 @ git+{HARNESS2_SOURCE}.git@{HARNESS2_REVISION}"
_INSTALL_HINT = f"uv pip install '{HARNESS2_REQUIREMENT}'"


def installation_status() -> dict[str, str | bool | None]:
    """Inspect package metadata without importing or executing the optional runtime."""
    version: str | None = None
    revision: str | None = None
    try:
        distribution = metadata.distribution("harness2")
    except metadata.PackageNotFoundError:
        pass
    else:
        version = distribution.version
        try:
            direct_url = json.loads(distribution.read_text("direct_url.json") or "{}")
            vcs = direct_url.get("vcs_info", {})
            if isinstance(vcs, dict) and isinstance(vcs.get("commit_id"), str):
                revision = vcs["commit_id"]
        except (TypeError, ValueError, AttributeError):
            pass
    return {
        "installed": version is not None,
        "version": version,
        "revision": revision,
        "expected_revision": HARNESS2_REVISION,
        "pinned": revision == HARNESS2_REVISION,
        "source": HARNESS2_SOURCE,
        "interactive_chat": False,
    }


def _run(module: str, arguments: tuple[str, ...]) -> None:
    state = installation_status()
    if not state["pinned"]:
        problem = (
            "is missing" if not state["installed"] else "does not match the reviewed revision"
        )
        raise click.ClickException(f"Harness² {problem}. Install it with:\n{_INSTALL_HINT}")
    try:
        result = subprocess.run(
            [sys.executable, "-m", f"harness2.cli.{module}", *arguments], check=False
        )
    except OSError as exc:
        raise click.ClickException(f"Could not start Harness²: {exc}") from exc
    if result.returncode:
        raise click.exceptions.Exit(
            result.returncode if result.returncode > 0 else 128 - result.returncode
        )


@click.group("harness2")
def harness2() -> None:
    """Harness² benchmark optimization (optional runtime, separate from chat)."""


@harness2.command("status")
@click.option("--json", "as_json", is_flag=True, help="Print package metadata as JSON.")
def status(as_json: bool) -> None:
    """Check the optional pinned runtime without model calls or setup changes."""
    state = installation_status()
    if as_json:
        click.echo(json.dumps(state, indent=2))
        return
    if state["pinned"]:
        click.echo(f"Harness² {state['version']} installed at {HARNESS2_REVISION}.")
    else:
        click.echo("Harness² optional runtime is missing or differs from the reviewed revision.")
        click.echo(f"Install: {_INSTALL_HINT}")
    click.echo("Benchmark optimization; use 'xwav harness2 demo' for a credential-free check.")


def _register_proxy(name: str, module: str, help_text: str) -> None:
    @harness2.command(
        name,
        help=help_text,
        add_help_option=False,
        context_settings={"ignore_unknown_options": True},
    )
    @click.argument("arguments", nargs=-1, type=click.UNPROCESSED)
    def command(arguments: tuple[str, ...]) -> None:
        _run(module, arguments)


_register_proxy(
    "demo",
    "demo",
    "Run deterministic local recursion without credentials. Pass --help for options.",
)
_register_proxy(
    "run", "run_sweep", "Run an explicitly requested benchmark sweep (model costs apply)."
)
_register_proxy(
    "check", "check", "Check an installed benchmark's prerequisites without model calls."
)
_register_proxy("judge", "judge", "Grade explicit benchmark results (model costs may apply).")
_register_proxy("report", "report", "Report explicit benchmark results. Pass --help for options.")

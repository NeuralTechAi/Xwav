"""Public Xvaw branding and configuration entry points."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from click.testing import CliRunner


@pytest.mark.parametrize("legacy_value", [None, "existing-setting"])
def test_xvaw_environment_prefix_is_available_before_runtime_imports(
    legacy_value: str | None,
) -> None:
    env = {"PATH": os.environ.get("PATH", ""), "XVAW_BRAND_TEST": "xvaw-setting"}
    if legacy_value is not None:
        env["OMNIGENT_BRAND_TEST"] = legacy_value
    expected = legacy_value or "xvaw-setting"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import omnigent, os; print(os.environ['OMNIGENT_BRAND_TEST'])",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == expected


@pytest.mark.parametrize("option", ["--help", "--version"])
def test_public_cli_identifies_xvaw(option: str) -> None:
    from omnigent.cli import cli

    result = CliRunner().invoke(cli, [option], prog_name="xvaw")
    assert result.exit_code == 0
    assert "xvaw" in result.output.lower()
    assert "omnigent" not in result.output.lower()

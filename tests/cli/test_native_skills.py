"""Native catalog CLI reads packaged resources without starting external tools."""

from __future__ import annotations

import json

from click.testing import CliRunner

from omnigent.cli_skills import skills


def test_native_skill_inventory_and_content() -> None:
    result = CliRunner().invoke(skills, ["list", "--json"])
    assert result.exit_code == 0, result.output
    catalog = json.loads(result.output)
    names = [entry["name"] for entry in catalog]
    assert names == sorted(set(names))
    assert {
        "git-workflow-and-versioning",
        "github-ops",
        "preproduction-tests",
        "karpathy-guidelines",
        "sol-pi",
        "google-skills",
        "context7-mcp",
        "reverse-engineer-anything",
        "graphify",
        "penetration-testing-with-strix",
    } <= set(names)
    for name in names:
        result = CliRunner().invoke(skills, ["show", name])
        assert result.exit_code == 0, result.output
        assert result.output.strip()


def test_native_skill_cli_errors_are_actionable() -> None:
    for command in ("show", "mcp-config"):
        result = CliRunner().invoke(skills, [command, "../not-a-skill"])
        assert result.exit_code != 0
        assert "Unknown native skill" in result.output


def test_native_skill_mcp_preset() -> None:
    result = CliRunner().invoke(skills, ["mcp-config", "context7-mcp"])
    assert result.exit_code == 0, result.output
    assert "context7" in result.output
    result = CliRunner().invoke(skills, ["mcp-config", "penetration-testing-with-strix"])
    assert result.exit_code != 0
    assert "does not include an MCP preset" in result.output


def test_native_skills_command_is_registered() -> None:
    from omnigent.cli import cli

    result = CliRunner().invoke(cli, ["skills", "--help"], prog_name="xwav")
    assert result.exit_code == 0, result.output
    assert "mcp-config" in result.output
    assert "Xwav" in result.output

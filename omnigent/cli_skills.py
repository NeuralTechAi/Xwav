"""Offline inspection of Xwav's packaged native skill catalog."""

from __future__ import annotations

import json

import click

from omnigent.spec.types import SkillSpec


def _catalog() -> list[SkillSpec]:
    from omnigent.native_skills import discover_native_skills

    return sorted(discover_native_skills("all"), key=lambda skill: skill.name)


def _find_skill(name: str) -> SkillSpec:
    for skill in _catalog():
        if skill.name == name:
            return skill
    raise click.ClickException(f"Unknown native skill {name!r}. Run 'xwav skills list'.")


@click.group()
def skills() -> None:
    """Inspect Xwav's native skills and optional MCP setup without running tools."""


@skills.command("list")
@click.option("--json", "as_json", is_flag=True, help="Print a machine-readable inventory.")
def list_skills(as_json: bool) -> None:
    """List bundled defaults; project and user skills take precedence at runtime."""
    catalog = _catalog()
    if as_json:
        click.echo(
            json.dumps(
                [
                    {
                        "name": skill.name,
                        "description": skill.description,
                        "path": str(skill.skill_dir) if skill.skill_dir else None,
                    }
                    for skill in catalog
                ],
                indent=2,
            )
        )
        return
    for skill in catalog:
        click.echo(f"{skill.name}\t{skill.description}")
    click.echo(f"\n{len(catalog)} native skills. Optional tools require their documented setup.")


@skills.command("show")
@click.argument("name")
def show_skill(name: str) -> None:
    """Read a native skill's instructions, including prerequisites."""
    skill = _find_skill(name)
    click.echo(skill.content)


@skills.command("mcp-config")
@click.argument("name")
def mcp_config(name: str) -> None:
    """Print an opt-in agent MCP preset; this does not install or start a server."""
    skill = _find_skill(name)
    preset = skill.skill_dir / "mcp.yaml" if skill.skill_dir else None
    if preset is None or not preset.is_file():
        raise click.ClickException(f"Native skill {name!r} does not include an MCP preset.")
    click.echo(preset.read_text(encoding="utf-8"), nl=False)

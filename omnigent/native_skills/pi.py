"""Opt-in Pi resource discovery using its supported extension lifecycle."""

from __future__ import annotations

import json
from pathlib import Path

from omnigent.native_skills import _content_key, discover_native_skills

PI_NATIVE_SKILLS_MIN_VERSION = (1, 4, 0)
PI_SKILL_CATALOG_ENV = "OMNIGENT_PI_SKILL_CATALOG"


def pi_native_skill_launch(
    skills_filter: str | list[str], version: tuple[int, int, int] | None
) -> tuple[list[str], dict[str, str]]:
    """Load defaults after Pi discovers user/project/package resources.

    Older Pi versions keep their existing skill behavior. The private manifest
    contains read-only paths and content hashes, never credentials or full prose.
    """
    if version is None or version < PI_NATIVE_SKILLS_MIN_VERSION or skills_filter == "none":
        return [], {}
    catalog = discover_native_skills(skills_filter)
    if not catalog:
        return [], {}
    manifest = [
        {
            "name": skill.name,
            "aliases": [skill.name, skill.display_name or skill.name],
            "directory": str(skill.skill_dir),
            "contentKey": _content_key(skill),
        }
        for skill in catalog
        if skill.skill_dir is not None
    ]
    extension = Path(__file__).with_name("pi_resources.cjs")
    return ["--extension", str(extension)], {PI_SKILL_CATALOG_ENV: json.dumps(manifest)}

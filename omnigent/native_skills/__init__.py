"""Offline native skills, loaded after user and agent-owned skills."""

from __future__ import annotations

import hashlib
from pathlib import Path

from omnigent.spec.types import SkillSpec


def native_skill_root() -> Path:
    """Return the installed, read-only skill resources directory."""
    return Path(__file__).parent / "skills"


def discover_native_skills(skills_filter: str | list[str] = "all") -> list[SkillSpec]:
    """Load packaged skills with the same selection rules as host skills."""
    from omnigent.spec.parser import _discover_skills, skill_matches_names

    if skills_filter == "none":
        return []
    names = set(skills_filter) if isinstance(skills_filter, list) else None
    return [
        skill
        for skill in _discover_skills(native_skill_root(), skipped=[])
        if skill.user_invocable and (names is None or skill_matches_names(skill, names))
    ]


def _skill_names(skill: SkillSpec) -> set[str]:
    return {
        name.rsplit(":", 1)[-1].casefold()
        for name in (
            skill.name,
            skill.display_name,
            skill.skill_dir.name if skill.skill_dir else None,
        )
        if name
    }


def _content_key(skill: SkillSpec) -> str | None:
    # Whitespace-only differences do not make a second copy of an upstream skill.
    content = " ".join(skill.content.split())
    return hashlib.sha256(content.encode()).hexdigest() if content else None


def merge_native_skills(
    existing: list[SkillSpec], skills_filter: str | list[str] = "all"
) -> list[SkillSpec]:
    """Append native defaults, preserving user overrides and hiding duplicate copies."""
    merged = list(existing)
    names: set[str] = set()
    contents: set[str] = set()
    for skill in existing:
        names.update(_skill_names(skill))
        if key := _content_key(skill):
            contents.add(key)
    for skill in discover_native_skills(skills_filter):
        aliases = _skill_names(skill)
        key = _content_key(skill)
        if names.intersection(aliases) or (key is not None and key in contents):
            continue
        merged.append(skill)
        names.update(aliases)
        if key:
            contents.add(key)
    return merged


def deduplicate_native_skill_dirs(skills: dict[str, Path]) -> dict[str, Path]:
    """Keep user directories and suppress equivalent native defaults in launch maps."""
    from omnigent.errors import OmnigentError
    from omnigent.spec.parser import _parse_skill

    root = native_skill_root().resolve()
    external: list[SkillSpec] = []
    for path in skills.values():
        if not path.resolve().is_relative_to(root):
            try:
                external.append(_parse_skill(path / "SKILL.md"))
            except (OSError, OmnigentError):
                continue
    selected = merge_native_skills(external)
    native_dirs = {skill.skill_dir for skill in selected[len(external) :]}
    return {
        name: path
        for name, path in skills.items()
        if not path.resolve().is_relative_to(root) or path in native_dirs
    }

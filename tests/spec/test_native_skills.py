"""Packaged defaults are loadable, filtered, and subordinate to existing skills."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from omnigent.native_skills import discover_native_skills, merge_native_skills, native_skill_root
from omnigent.spec.skill_sources import resolve_session_skills
from omnigent.spec.types import AgentSpec


def test_catalog_provenance_and_unique_resources():
    catalog = discover_native_skills()
    assert len(catalog) == 39
    assert len({skill.name for skill in catalog}) == len(catalog)
    assert len({" ".join(skill.content.split()) for skill in catalog}) == len(catalog)
    sources = json.loads((native_skill_root().parent / "sources.json").read_text())
    sources += json.loads((native_skill_root().parent / "integrations.json").read_text())[
        "sources"
    ]
    assert {name for source in sources for name in source["skills"]} == {s.name for s in catalog}
    for source in sources:
        if source.get("origin") == "first-party":
            assert source["repository"] == "https://github.com/NeuralTechAi/Xwav"
            assert source["revision"] is None
        else:
            assert len(source["revision"]) == 40
    for skill in catalog:
        assert skill.skill_dir is not None
        assert (skill.skill_dir / "SKILL.md").is_file()
        assert any(path.name.startswith("LICENSE") for path in skill.skill_dir.iterdir())


def test_native_filters():
    assert discover_native_skills("none") == []
    assert [skill.name for skill in discover_native_skills(["unslop"])] == ["unslop"]
    assert discover_native_skills(["not-installed"]) == []


@pytest.mark.parametrize("override", ["same-name", "plugin-alias", "same-content"])
@pytest.mark.parametrize(
    "name",
    [
        "unslop",
        "github-ops",
        "git-workflow-and-versioning",
        "preproduction-tests",
        "karpathy-guidelines",
        "sol-pi",
        "google-skills",
    ],
)
def test_user_skills_win_without_native_duplicates(override, name):
    native = discover_native_skills([name])[0]
    user = replace(native, skill_dir=None)
    if override == "plugin-alias":
        user = replace(user, name=f"my-plugin:{name}", content="User customized instructions")
    elif override == "same-content":
        user = replace(
            user, name="custom-editing", content="  " + native.content.replace("\n", "  ")
        )
    else:
        user = replace(user, content="User customized instructions")
    assert merge_native_skills([user], [name]) == [user]


@pytest.mark.parametrize("hidden", [False, True])
def test_bundle_alias_reserves_native_name_in_session(tmp_path, monkeypatch, hidden):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    native = discover_native_skills(["unslop"])[0]
    user = replace(native, name="my-plugin:unslop", skill_dir=None, user_invocable=not hidden)
    spec = AgentSpec(spec_version=1, skills=[user], skills_filter=["unslop"])
    assert resolve_session_skills(spec, (tmp_path,), None) == ([] if hidden else [user])


@pytest.mark.parametrize("name", ["unslop", "karpathy-guidelines", "sol-pi", "google-skills"])
def test_claude_and_codex_launch_load_resources(tmp_path, monkeypatch, name):
    from omnigent.inner.bundle_skills import claude_agents_skill_args
    from omnigent.inner.codex_executor import codex_skill_sources, select_codex_skill_dirs

    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    args = claude_agents_skill_args(tmp_path / "bridge", (tmp_path,), [name])
    assert args[0] == "--add-dir"
    overlay = Path(args[1]) / ".claude" / "skills" / name / "SKILL.md"
    assert overlay.read_text() == (native_skill_root() / name / "SKILL.md").read_text()
    sources = codex_skill_sources(None, tmp_path / "home")
    selected = select_codex_skill_dirs([name], sources)
    assert selected == {name: native_skill_root() / name}
    assert select_codex_skill_dirs("none", sources) == {}


@pytest.mark.parametrize("harness", ["pi", "pi-native", "cursor-native"])
def test_unbridged_harness_does_not_advertise_native_defaults(tmp_path, monkeypatch, harness):
    from omnigent.spec.skill_sources import SkillSourceContext, resolve_harness_skills

    monkeypatch.setattr(
        "omnigent.spec.skill_sources._SKILL_SOURCES",
        {"pi": lambda ctx: [], "cursor": lambda ctx: []},
    )
    ctx = SkillSourceContext(
        roots=(tmp_path,), home=tmp_path, skills_filter="all", bundle_dir=None
    )
    assert resolve_harness_skills(ctx, harness) == []


def test_karpathy_skill_is_pinned_unmodified_and_attributed():
    import hashlib

    sources = json.loads((native_skill_root().parent / "integrations.json").read_text())["sources"]
    matches = [source for source in sources if "karpathy-guidelines" in source["skills"]]
    assert len(matches) == 1
    source = matches[0]
    directory = native_skill_root() / "karpathy-guidelines"
    assert (
        hashlib.sha256((directory / "SKILL.md").read_bytes()).hexdigest()
        == source["upstream_skill_sha256"]
    )
    manifest = json.loads((directory / "LICENSE.upstream.json").read_text())
    assert manifest["license"] == source["license"] == "MIT"
    assert manifest["author"]["name"] == "forrestchang"
    assert manifest["skills"] == ["./skills/karpathy-guidelines"]
    assert [skill.name for skill in discover_native_skills(["karpathy-guidelines"])] == [
        "karpathy-guidelines"
    ]


def test_google_collection_integrity_and_single_discovery_entry():
    import hashlib

    skill = discover_native_skills(["google-skills"])[0]
    directory = skill.skill_dir
    assert directory is not None
    manifest = json.loads((directory / "catalog.json").read_text())
    source = next(
        entry
        for entry in json.loads((directory.parent.parent / "integrations.json").read_text())[
            "sources"
        ]
        if entry["repository"] == "https://github.com/google/skills"
    )
    assert manifest["revision"] == source["revision"]
    assert len(manifest["skills"]) == source["upstream_skill_count"] == 177
    assert len({entry["name"] for entry in manifest["skills"]}) == 177
    assert list(directory.rglob("SKILL.md")) == [directory / "SKILL.md"]
    bodies = set()
    for entry in manifest["skills"]:
        path = directory / entry["path"]
        assert path.is_file()
        assert entry["path"] in (directory / "references" / f"{entry['topic']}.md").read_text()
        body = " ".join(path.read_text().split("---", 2)[2].split())
        assert body not in bodies
        bodies.add(body)
    for relative, checksum in manifest["files"].items():
        path = directory / relative
        assert path.resolve().is_relative_to(directory.resolve())
        assert not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == checksum


def test_google_staged_loading_reads_only_selected_guidance():
    from omnigent.tools.base import ToolContext
    from omnigent.tools.builtins.load_skill import LoadSkillTool
    from omnigent.tools.builtins.read_skill_file import ReadSkillFileTool

    native = discover_native_skills(["google-skills"])[0]
    ctx = ToolContext(task_id="google-discovery", agent_id="test")
    loader = LoadSkillTool([native], skills_filter="none")
    schema = loader.get_schema()["function"]["description"]
    assert "google-skills:" in schema
    assert "agent-platform-alert-configuration" not in schema
    overview = loader.invoke(json.dumps({"name": "google-skills"}), ctx)
    assert len(overview) < 12000
    assert "references/ai-and-machine-learning.md" in overview
    assert "library/cloud/gemini-api/INSTRUCTIONS.md" not in overview
    reader = ReadSkillFileTool([native])
    topic = reader.invoke(
        json.dumps({"skill_name": native.name, "path": "references/ai-and-machine-learning.md"}),
        ctx,
    )
    assert "library/cloud/gemini-api/INSTRUCTIONS.md" in topic
    selected = reader.invoke(
        json.dumps(
            {"skill_name": native.name, "path": "library/cloud/gemini-api/INSTRUCTIONS.md"}
        ),
        ctx,
    )
    assert "# Gemini API in Agent Platform" in selected
    assert "Configures best-practice alerting policies" not in selected
    attribution = reader.invoke(
        json.dumps(
            {
                "skill_name": native.name,
                "path": "library/cloud/gemini-api/references/attribution.md",
            }
        ),
        ctx,
    )
    assert "CLOUDSDK_METRICS_REQUEST_ATTRIBUTION" in attribution

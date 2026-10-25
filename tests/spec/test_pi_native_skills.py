"""Pi skill resource discovery runs offline and preserves the vendor catalog."""

from __future__ import annotations

import json
import os
import select
import shutil
import subprocess
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from omnigent.native_skills import discover_native_skills
from omnigent.native_skills.pi import PI_SKILL_CATALOG_ENV, pi_native_skill_launch


@pytest.mark.parametrize("version", [None, (0, 84, 2), (1, 3, 9)])
def test_older_pi_keeps_existing_resources(version):
    assert pi_native_skill_launch("all", version) == ([], {})


@pytest.mark.parametrize("skills_filter", ["all", "none", ["unslop"], ["karpathy-guidelines"]])
def test_pi_rpc_executor_passes_selected_native_resources(skills_filter):
    from omnigent.inner.pi_executor import PiExecutor

    with patch("omnigent.harnesses.pi_native.main.pi_version", return_value=(1, 4, 0)):
        executor = PiExecutor(pi_path="/bin/pi", skills_filter=skills_filter)
    if skills_filter == "none":
        assert "--no-skills" in executor._extra_args
        assert PI_SKILL_CATALOG_ENV not in executor._env
    else:
        assert any(path.endswith("pi_resources.cjs") for path in executor._extra_args)
        catalog = json.loads(executor._env[PI_SKILL_CATALOG_ENV])
        expected = (
            set(skills_filter)
            if isinstance(skills_filter, list)
            else {skill.name for skill in discover_native_skills()}
        )
        assert {entry["name"] for entry in catalog} == expected


@pytest.mark.parametrize("name", ["unslop", "karpathy-guidelines"])
def test_pi_runtime_name_and_content_overrides(tmp_path: Path, name):
    args, env = pi_native_skill_launch("all", (1, 4, 0))
    catalog = json.loads(env[PI_SKILL_CATALOG_ENV])
    unslop = next(skill for skill in discover_native_skills() if skill.name == name)
    copy = tmp_path / "renamed-copy" / "SKILL.md"
    copy.parent.mkdir()
    copy.write_text("---\nname: renamed-copy\ndescription: User copy\n---\n" + unslop.content)
    script = """
const mod = require(process.argv[1]);
const catalog = JSON.parse(process.argv[2]);
const commands = [
 {name:'skill:context7-mcp',source:'skill',sourceInfo:{path:'/missing/user/SKILL.md'}},
 {name:'skill:renamed-copy',source:'skill',sourceInfo:{path:process.argv[3]}}
];
process.stdout.write(JSON.stringify(mod.selectedPaths(catalog, commands)));
"""
    result = subprocess.run(
        ["node", "-e", script, args[1], json.dumps(catalog), str(copy)],
        capture_output=True,
        text=True,
        check=True,
    )
    selected = {Path(path).name for path in json.loads(result.stdout)}
    assert selected == {skill["name"] for skill in catalog} - {name, "context7-mcp"}


@pytest.mark.parametrize("skills_filter", ["all", "none", ["unslop"], ["karpathy-guidelines"]])
def test_real_pi_rpc_reports_only_loaded_native_commands(tmp_path: Path, skills_filter):
    # The optional local runtime is installed by the acceptance setup. No network
    # resolution, credentials, prompts, or model calls are permitted in this test.
    root = Path(__file__).parents[2]
    cli = (
        root
        / ".omnigent/harness-tools/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js"
    )
    if not cli.is_file() or not shutil.which("node"):
        pytest.skip("Pi 1.4 local acceptance runtime is not installed")
    args, skill_env = pi_native_skill_launch(skills_filter, (1, 4, 0))
    user = tmp_path / "agent"
    project = tmp_path / "workspace"
    project.mkdir()
    existing = project / ".pi/skills/unslop/SKILL.md"
    existing.parent.mkdir(parents=True)
    existing.write_text(
        "---\nname: unslop\ndescription: Project override\n---\nUser instructions."
    )
    duplicate = project / ".pi/skills/renamed-simplification/SKILL.md"
    duplicate.parent.mkdir(parents=True)
    native_copy = discover_native_skills(["code-simplification"])[0]
    duplicate.write_text(
        "---\nname: renamed-simplification\ndescription: Project copy\n---\n" + native_copy.content
    )
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(tmp_path),
        "PI_CODING_AGENT_DIR": str(user),
        **skill_env,
    }
    command = [
        "node",
        str(cli),
        "--mode",
        "rpc",
        "--no-session",
        "--no-extensions",
        "--no-context-files",
        "--no-prompt-templates",
        "--no-themes",
        "--no-mcp",
        "--approve",
        *args,
    ]
    if skills_filter != "all":
        command.append("--no-skills")
    process = subprocess.Popen(
        command,
        cwd=project,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write('{"id":"skills","type":"get_commands"}\n')
        process.stdin.flush()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            readable, _, _ = select.select([process.stdout], [], [], 1)
            if not readable:
                continue
            line = process.stdout.readline()
            if not line:
                pytest.fail("Pi exited before reporting the skill catalog")
            response = json.loads(line)
            if response.get("id") == "skills":
                break
        else:
            pytest.fail("Pi did not report its skill catalog within 30 seconds")
        assert response["success"] is True
        commands = {
            entry["name"]: entry
            for entry in response["data"]["commands"]
            if entry["source"] == "skill"
        }
        expected = (
            set()
            if skills_filter == "none"
            else {f"skill:{name}" for name in skills_filter}
            if isinstance(skills_filter, list)
            else {f"skill:{skill.name}" for skill in discover_native_skills()}
        )
        if skills_filter == "all":
            expected.remove("skill:code-simplification")
            expected.add("skill:renamed-simplification")
        assert set(commands) == expected
        if skills_filter == "all":
            assert commands["skill:unslop"]["sourceInfo"]["path"] == str(existing)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

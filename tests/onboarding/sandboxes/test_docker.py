"""Local job containers are separate and never mount the developer workspace."""

from unittest.mock import patch

import click
import pytest
from pydantic import ValidationError

from omnigent.onboarding.sandboxes.base import RemoteCommandResult
from omnigent.onboarding.sandboxes.docker import DockerSandboxConfig, DockerSandboxLauncher


@pytest.mark.parametrize("env", [["TOKEN=secret"], ["--privileged"], ["a b"]])
def test_environment_accepts_names_only(env):
    with pytest.raises(ValidationError):
        DockerSandboxConfig(env=env)


def test_fresh_containers_have_resource_limits_without_shared_volumes():
    launcher = DockerSandboxLauncher()
    with patch.object(
        launcher, "_docker", return_value=RemoteCommandResult(0, "a" * 64, "")
    ) as docker:
        launcher.provision("project-a")
        launcher.provision("project-b")
    first, second = [call.args for call in docker.call_args_list]
    assert first[first.index("--name") + 1] != second[second.index("--name") + 1]
    assert "--cap-drop=ALL" in first
    assert "--security-opt=no-new-privileges" in first
    assert "--memory" in first and "--pids-limit" in first
    assert not {"--volume", "-v", "--mount", "--privileged"}.intersection(first)


def test_bootstrap_secret_is_passed_on_stdin():
    launcher = DockerSandboxLauncher()
    sandbox_id = "a" * 64
    with patch.object(
        launcher,
        "_docker",
        side_effect=[RemoteCommandResult(0, "true", ""), RemoteCommandResult(0, "ok", "")],
    ) as docker:
        launcher.run(sandbox_id, "secret-token-command")
    call = docker.call_args_list[-1]
    assert "secret-token-command" not in call.args
    assert call.kwargs == {"command": "secret-token-command"}


def test_refuses_to_remove_unmanaged_container():
    launcher = DockerSandboxLauncher()
    with patch.object(
        launcher, "_docker", return_value=RemoteCommandResult(0, "false", "")
    ) as docker:
        with pytest.raises(click.ClickException, match="not an Xwav"):
            launcher.terminate("a" * 64)
    assert docker.call_count == 1


def test_missing_container_cleanup_is_idempotent():
    launcher = DockerSandboxLauncher()
    with patch.object(
        launcher, "_docker", return_value=RemoteCommandResult(1, "", "No such container")
    ) as docker:
        launcher.terminate("a" * 64)
    assert docker.call_count == 1


def test_codex_login_inheritance_is_explicit_and_uses_private_stdin(tmp_path, monkeypatch):
    import json
    from unittest.mock import call

    home = tmp_path / "codex"
    home.mkdir()
    credential = json.dumps({"OPENAI_API_KEY": "test-key-never-in-argv"})
    (home / "auth.json").write_text(credential)
    monkeypatch.setenv("CODEX_HOME", str(home))
    launcher = DockerSandboxLauncher(config=DockerSandboxConfig(inherit_codex_login=True))
    sandbox_id = "a" * 64
    with patch.object(
        launcher,
        "_docker",
        side_effect=[
            RemoteCommandResult(0, sandbox_id, ""),
            RemoteCommandResult(0, "true", ""),
            RemoteCommandResult(0, "", ""),
        ],
    ) as docker:
        assert launcher.provision("project") == sandbox_id
    transfer = docker.call_args_list[-1]
    assert credential not in str(transfer.args)
    assert transfer.kwargs["command"] == credential
    assert "0o600" in transfer.args[-1]
    assert (
        call(
            "exec",
            "--interactive",
            sandbox_id,
            "python3",
            "-c",
            transfer.args[-1],
            command=credential,
        )
        == transfer
    )


def test_failed_codex_login_copy_removes_new_container():
    launcher = DockerSandboxLauncher(config=DockerSandboxConfig(inherit_codex_login=True))
    sandbox_id = "a" * 64
    with (
        patch.object(launcher, "_docker", return_value=RemoteCommandResult(0, sandbox_id, "")),
        patch.object(
            launcher, "install_codex_login", side_effect=click.ClickException("Login missing")
        ),
        patch.object(launcher, "terminate") as terminate,
    ):
        with pytest.raises(click.ClickException, match="Login missing"):
            launcher.provision("project")
        terminate.assert_called_once_with(sandbox_id)


def test_codex_login_copy_refuses_without_opt_in():
    with pytest.raises(click.ClickException, match="not enabled"):
        DockerSandboxLauncher().install_codex_login("a" * 64)

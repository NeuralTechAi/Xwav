"""Real Git repositories exercise stage/commit without network or user config."""

import json
import subprocess

import pytest

from omnigent.workspace_git import git_command, git_request


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    for key, value in [
        ("user.name", "Test"),
        ("user.email", "test@example.test"),
        ("commit.gpgsign", "false"),
    ]:
        subprocess.run(["git", "-C", str(tmp_path), "config", key, value], check=True)
    return tmp_path


def test_stage_and_commit_keep_ignored_and_unstaged_edits_outside_commit(repo):
    (repo / ".gitignore").write_text("secret.env\n")
    (repo / "secret.env").write_text("private")
    (repo / "app.txt").write_text("reviewed version")

    def call(action, **kw):
        return git_request({"workspace": str(repo), "action": action, **kw})

    assert call("status")["unstaged_count"] == 2
    staged = call("stage")
    assert staged["state"] == "staged" and staged["staged_count"] == 2
    (repo / "app.txt").write_text("later unstaged edit")
    committed = call("commit", token=staged["token"], message="Add app")
    assert committed["state"] == "committed"
    assert committed["unstaged_count"] == 1
    assert (
        subprocess.check_output(["git", "-C", str(repo), "show", "HEAD:app.txt"]).decode()
        == "reviewed version"
    )
    assert len(committed["commit"]) == 40
    assert not (repo / ".git/refs/remotes").exists()


def test_commit_rejects_changed_index_empty_message_and_empty_index(repo):
    def call(action, **kw):
        return git_request({"workspace": str(repo), "action": action, **kw})

    (repo / "app").write_text("one")
    staged = call("stage")
    (repo / "app").write_text("two")
    call("stage")
    assert "changed" in call("commit", token=staged["token"], message="Old review")["message"]
    current = call("status")
    assert "commit message" in call("commit", token=current["token"], message="  ")["message"]
    assert call("commit", token=current["token"], message="Fresh review")["state"] == "committed"
    empty = call("status")
    assert "Stage changes" in call("commit", token=empty["token"], message="Duplicate")["message"]


def test_stage_tracks_deletions_and_renames(repo):
    (repo / "old").write_text("contents")
    (repo / "deleted").write_text("remove")
    staged = git_request({"workspace": str(repo), "action": "stage"})
    git_request(
        {
            "workspace": str(repo),
            "action": "commit",
            "token": staged["token"],
            "message": "Initial",
        }
    )
    (repo / "old").rename(repo / "renamed")
    (repo / "deleted").unlink()
    result = git_request({"workspace": str(repo), "action": "stage"})
    assert result["staged_count"] == 2
    assert {file["path"] for file in result["files"]} == {"renamed", "deleted"}


def test_transport_quotes_message_and_does_not_stage_parent_repo(repo):
    child = repo / "child"
    child.mkdir()
    assert (
        "repository root" in git_request({"workspace": str(child), "action": "stage"})["message"]
    )
    command = git_command(
        str(repo), {"action": "status", "message": "$(touch injected)\nXWAV_GIT_ACTION"}
    )
    result = subprocess.run(
        ["sh", "-c", command], cwd=repo, capture_output=True, text=True, check=True
    )
    assert json.loads(result.stdout)["state"] == "ready"
    assert not (repo / "injected").exists()


def test_non_repository_returns_actionable_error(tmp_path):
    result = git_request({"workspace": str(tmp_path), "action": "status"})
    assert result["state"] == "not_git"
    assert not (tmp_path / ".git").exists()
    (tmp_path / "app.txt").write_text("source")
    (tmp_path / ".env").write_text("private")
    initialized = git_request({"workspace": str(tmp_path), "action": "init"})
    assert initialized["state"] == "ready"
    assert {file["path"] for file in initialized["files"]} == {"app.txt"}
    assert (tmp_path / "app.txt").read_text() == "source"


def test_new_project_can_commit_with_explicit_identity_without_global_config(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "user.useConfigOnly")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")
    for key in (
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
        "EMAIL",
    ):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / "app").write_text("source")
    request = {"workspace": str(tmp_path)}
    git_request({**request, "action": "init"})
    staged = git_request({**request, "action": "stage"})
    assert staged["author_required"] is True
    commit = {**request, "action": "commit", "token": staged["token"], "message": "Initial"}
    assert "author name and email" in git_request(commit)["message"]
    result = git_request(
        {**commit, "author_name": "Project Author", "author_email": "author@example.test"}
    )
    assert result["state"] == "committed"
    assert (
        subprocess.check_output(["git", "-C", str(tmp_path), "show", "-s", "--format=%an <%ae>"])
        .decode()
        .strip()
        == "Project Author <author@example.test>"
    )
    assert (
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "--get", "user.name"], capture_output=True
        ).returncode
        == 1
    )

"""File reverts preserve chat-independent state, isolation and safe recovery."""

import json
from pathlib import Path

import pytest

from omnigent import workspace_checkpoints as history


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    root = tmp_path / "project"
    root.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(root)
    return root


def request(action, anchor="message-one", **kwargs):
    return history.checkpoint_request(
        {"session_id": "job-one", "anchor": anchor, "action": action, **kwargs}
    )


def test_restore_files_additions_deletions_modes_and_undo(workspace):
    (workspace / "app.txt").write_text("before")
    (workspace / "app.txt").chmod(0o755)
    (workspace / "deleted.txt").write_text("restore me")
    (workspace / "node_modules").mkdir()
    (workspace / "node_modules" / "keep").write_text("dependency")
    (workspace / ".git").mkdir()
    (workspace / ".git" / "HEAD").write_text("original ref")
    assert request("capture")["state"] == "ready"
    (workspace / "app.txt").write_text("after")
    (workspace / "app.txt").chmod(0o644)
    (workspace / "deleted.txt").unlink()
    (workspace / "new.txt").write_text("new")
    (workspace / ".git" / "HEAD").write_text("keep current ref")
    plan = request("plan")
    assert plan["count"] == 3
    result = request("apply", token=plan["token"])
    assert result["state"] == "restored"
    assert (workspace / "app.txt").read_text() == "before"
    assert (workspace / "app.txt").stat().st_mode & 0o777 == 0o755
    assert (workspace / "deleted.txt").read_text() == "restore me"
    assert not (workspace / "new.txt").exists()
    assert (workspace / "node_modules" / "keep").read_text() == "dependency"
    assert (workspace / ".git" / "HEAD").read_text() == "keep current ref"
    undo = request("plan", result["backup_id"])
    assert request("apply", result["backup_id"], token=undo["token"])["state"] == "restored"
    assert (workspace / "app.txt").read_text() == "after"
    assert (workspace / "new.txt").read_text() == "new"
    assert not (workspace / "deleted.txt").exists()


def test_changed_files_require_another_review(workspace):
    (workspace / "app").write_text("before")
    request("capture")
    (workspace / "app").write_text("edited")
    plan = request("plan")
    (workspace / "app").write_text("new manual edit")
    assert request("apply", token=plan["token"])["state"] == "conflict"
    assert (workspace / "app").read_text() == "new manual edit"


def test_checkpoint_is_idempotent_and_other_sessions_cannot_restore_it(workspace):
    (workspace / "app").write_text("before")
    request("capture")
    (workspace / "app").write_text("after")
    request("capture")
    plan = request("plan")
    assert plan["count"] == 1
    assert (
        history.checkpoint_request(
            {"session_id": "other-job", "anchor": "message-one", "action": "plan"}
        )["state"]
        == "unavailable"
    )
    assert request("plan", "older-message")["state"] == "unavailable"


def test_restore_never_follows_new_parent_symlink(workspace, tmp_path):
    folder = workspace / "src"
    folder.mkdir()
    (folder / "app.txt").write_text("before")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "app.txt").write_text("outside safe")
    request("capture")
    (folder / "app.txt").unlink()
    folder.rmdir()
    folder.symlink_to(outside, target_is_directory=True)
    plan = request("plan")
    assert request("apply", token=plan["token"])["state"] == "restored"
    assert not folder.is_symlink()
    assert (folder / "app.txt").read_text() == "before"
    assert (outside / "app.txt").read_text() == "outside safe"


def test_corrupt_checkpoint_does_not_change_any_files(workspace):
    (workspace / "app").write_text("before")
    request("capture")
    (workspace / "app").write_text("after")
    storage = next((Path.home() / ".omnigent" / "checkpoints").iterdir())
    manifest = json.loads(next(storage.glob("*.json")).read_text())
    (storage / "blobs" / manifest["files"]["app"]["blob"]).write_text("damaged")
    assert request("plan")["state"] == "unavailable"
    assert (workspace / "app").read_text() == "after"


def test_failed_restore_rolls_back_partial_writes(workspace, monkeypatch):
    for name in ["a", "b"]:
        (workspace / name).write_text("before")
    request("capture")
    for name in ["a", "b"]:
        (workspace / name).write_text("after")
    plan = request("plan")
    original = history._write
    failed = False

    def fail_once(path, content, mode=0o600):
        nonlocal failed
        if path == workspace / "b" and not failed:
            failed = True
            raise OSError("simulated write failure")
        original(path, content, mode)

    monkeypatch.setattr(history, "_write", fail_once)
    assert request("apply", token=plan["token"])["state"] == "unavailable"
    assert [(workspace / name).read_text() for name in ["a", "b"]] == ["after", "after"]


def test_capture_budget_refuses_incomplete_snapshots(workspace, monkeypatch):
    (workspace / "app").write_text("too large")
    monkeypatch.setattr(history, "MAX_BYTES", 1)
    assert request("capture")["state"] == "unavailable"
    assert request("plan")["state"] == "unavailable"


def test_checkpoint_transport_quotes_data_and_runs_on_existing_runner(workspace):
    import subprocess

    from omnigent.server.workspace_history import checkpoint_command

    anchor = "message'\\n$(touch should-not-exist)"
    result = subprocess.run(
        checkpoint_command("job", anchor, "capture"),
        shell=True,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout)["state"] == "ready"
    assert not (workspace / "should-not-exist").exists()


@pytest.mark.asyncio
async def test_capture_is_before_delivery_and_skips_running_jobs():
    import httpx

    from omnigent.server.workspace_history import capture_before_message

    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={"status": "idle"}
            if request.method == "GET"
            else {"stdout": '{"state":"ready"}'},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle), base_url="http://runner"
    ) as client:
        await capture_before_message(client, "job", "message")
    assert [call.method for call in calls] == ["GET", "POST"]
    assert '"action": "capture"' in json.loads(calls[1].content)["command"]
    calls.clear()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: (
                calls.append(request) or httpx.Response(200, json={"status": "running"})
            )
        ),
        base_url="http://runner",
    ) as client:
        await capture_before_message(client, "job", "message")
    assert [call.method for call in calls] == ["GET"]


def test_selected_workspace_overrides_resource_shell_directory(workspace):
    selected = workspace.parent / "selected-project"
    selected.mkdir()
    (selected / "app").write_text("selected before")
    (workspace / "app").write_text("other project unchanged")
    parameters = {"session_id": "selected-job", "anchor": "message", "workspace": str(selected)}
    assert history.checkpoint_request({**parameters, "action": "capture"})["state"] == "ready"
    (selected / "app").write_text("selected after")
    plan = history.checkpoint_request({**parameters, "action": "plan"})
    assert (
        history.checkpoint_request({**parameters, "action": "apply", "token": plan["token"]})[
            "state"
        ]
        == "restored"
    )
    assert (selected / "app").read_text() == "selected before"
    assert (workspace / "app").read_text() == "other project unchanged"


def test_input_cannot_choose_another_messages_checkpoint():
    from omnigent.server.routes._sessions.helpers import _build_new_item
    from omnigent.server.routes._sessions.orchestration import _new_external_conversation_item
    from omnigent.server.schemas import SessionEventInput

    body = SessionEventInput(
        type="message",
        data={
            "role": "user",
            "content": [{"type": "input_text", "text": "edit"}],
            "stable_id": "a" * 32,
            "workspace_checkpoint_id": "forged",
        },
    )
    item = _build_new_item(body, "turn", adopt_stable_id=True)
    assert item.data.workspace_checkpoint_id == "a" * 32
    external = _new_external_conversation_item(
        "job",
        SessionEventInput(
            type="external_conversation_item",
            data={
                "item_type": "message",
                "response_id": "turn",
                "source_id": "source",
                "item_data": {
                    "role": "user",
                    "content": [{"type": "input_text", "text": "edit"}],
                    "workspace_checkpoint_id": "forged",
                },
            },
        ),
    )
    assert external.data.workspace_checkpoint_id is None


def test_changes_compare_request_boundaries_and_never_restore_files(workspace):
    (workspace / "app.py").write_text("old\n")
    (workspace / "deleted").write_text("gone\n")
    request("capture")
    (workspace / "app.py").write_text("new\nextra\n")
    (workspace / "deleted").unlink()
    (workspace / "new").write_text("added\n")
    request("capture", "next-request")
    (workspace / "app.py").write_text("a later turn\n")
    summary = request("changes", end_anchor="next-request")
    assert summary["count"] == 3
    assert summary["files"] == [
        {"path": "app.py", "status": "modified", "additions": 2, "deletions": 1},
        {"path": "deleted", "status": "deleted", "additions": 0, "deletions": 1},
        {"path": "new", "status": "added", "additions": 1, "deletions": 0},
    ]
    detail = request("changes", end_anchor="next-request", path="app.py")["files"][0]
    assert "+extra" in detail["diff"] and "a later turn" not in detail["diff"]
    assert (workspace / "app.py").read_text() == "a later turn\n"
    assert "+a later turn" in request("changes", path="app.py")["files"][0]["diff"]
    assert request("changes", path="../../outside")["state"] == "unavailable"
    assert request("changes", end_anchor="missing")["state"] == "unavailable"


def test_changes_handle_binary_links_modes_limits_and_empty_workspace(workspace, tmp_path):
    (workspace / "binary").write_bytes(b"\x00old")
    (workspace / "mode").write_text("same\n")
    request("capture")
    assert request("changes")["count"] == 0
    (workspace / "binary").write_bytes(b"\x00new")
    (workspace / "mode").chmod(0o755)
    (workspace / "link").symlink_to(tmp_path / "outside")
    (workspace / "large").write_bytes(b"x" * (256 * 1024 + 1))
    rows = {row["path"]: row for row in request("changes")["files"]}
    assert rows["binary"]["additions"] is None
    assert rows["large"]["additions"] is None
    assert rows["mode"]["additions"] == 0
    assert "metadata" in request("changes", path="mode")["files"][0]["note"]
    assert "Symlink" in request("changes", path="link")["files"][0]["diff"]
    for index in range(205):
        (workspace / f"file{index:03}").write_text("new\n")
    summary = request("changes")
    assert summary["count"] == 209 and len(summary["files"]) == 200
    assert request("changes", path="mode")["files"][0]["path"] == "mode"


def test_changes_report_newline_only_edits(workspace):
    (workspace / "app").write_text("same")
    request("capture")
    (workspace / "app").write_text("same\n")
    detail = request("changes", path="app")["files"][0]
    assert detail["additions"] == detail["deletions"] == 1
    assert "No newline at end of file" in detail["diff"]

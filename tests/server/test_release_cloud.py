"""Cloud orchestration contracts plus a real generated-worker web build."""

import io
import json
import os
import stat
import subprocess
import sys
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from omnigent import preproduction_runtime as coordinator
from omnigent import release_cloud as cloud
from omnigent import release_runtime as runtime
from omnigent.server.releases import release_command


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    monkeypatch.setenv("GH_TOKEN", "test-token-never-log")
    monkeypatch.setenv("XWAV_BUILD_CACHE", str(tmp_path / "tools"))
    return root


def prepare(root):
    command = release_command(
        "cloud-job", str(root), "prepare", engine="github", repository="owner/app"
    )
    assert len(command) < 65536
    result = subprocess.run(["bash", "-c", command], capture_output=True, text=True, check=True)
    payload = json.loads(result.stdout)
    assert payload["state"] == "empty", payload
    return payload


def commit(root):
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.test",
            "commit",
            "-qm",
            "test project",
        ],
        check=True,
    )
    return cloud.git(root, "rev-parse", "HEAD")


def bundle(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


def test_prepare_transport_is_idempotent_and_generates_restricted_workflow(project):
    prepare(project)
    first = (project / ".gitignore").read_text()
    prepare(project)
    assert (project / ".gitignore").read_text() == first
    workflow = yaml.safe_load((project / ".github/workflows/xwav-release.yml").read_text())
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["release"]["timeout-minutes"] == 45
    assert "macos-15" in workflow["jobs"]["release"]["runs-on"]
    assert "xwav-production" in workflow["jobs"]["release"]["environment"]
    assert workflow["jobs"]["release"]["steps"][0]["with"]["persist-credentials"] is False
    assert "test-token-never-log" not in "".join(
        p.read_text() for p in (project / ".xwav/cloud").glob("*.py")
    )
    assert cloud.settings(project)["repository"] == "owner/app"
    # Source is modified only by explicit preparation; status does not publish.
    result = subprocess.run(
        ["bash", "-c", release_command("cloud-job", str(project), "status", engine="github")],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["state"] == "empty"


@pytest.mark.parametrize(
    "repository",
    ["https://github.com/owner/app", "../app", "owner/a;touch bad", "owner/app/token"],
)
def test_prepare_rejects_invalid_repository(project, repository):
    with pytest.raises(ValueError):
        cloud.prepare(project, repository, {})


def test_prepare_refuses_existing_custom_workflow_and_symlink(project, tmp_path):
    workflow = project / ".github/workflows/xwav-release.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("custom workflow")
    result = subprocess.run(
        [
            "bash",
            "-c",
            release_command("a", str(project), "prepare", engine="github", repository="owner/app"),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "would replace" in json.loads(result.stdout)["error"]
    assert workflow.read_text() == "custom workflow"
    assert not (project / ".xwav").exists()
    (project / ".gitignore").symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError, match="symlink"):
        cloud.prepare(project, "owner/app", {})


def test_preflight_rejects_dirty_source_and_absent_auth(project, monkeypatch):
    prepare(project)
    with pytest.raises(ValueError, match="Commit and push"):
        cloud.preflight(project, "web", "build", "testing", "vercel")
    commit(project)
    assert cloud.preflight(project, "web", "build", "testing", "vercel")[2] == "xwav-build"
    (project / "new.txt").write_text("unsaved in cloud")
    assert not cloud.plan(project, "web", "build", "testing", "vercel")["ready"]
    monkeypatch.delenv("GH_TOKEN")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(cloud.shutil, "which", lambda _name: None)
    with pytest.raises(ValueError, match="Connect GitHub"):
        cloud.token()


def test_connection_checks_production_protection_and_secret_names(project, monkeypatch):
    prepare(project)
    commit(project)
    protected = False
    names = []

    def api(_repo, path, *_args, **_kwargs):
        if "/actions/workflows/" in path:
            return {"state": "active"}
        if path.endswith("secrets?per_page=100"):
            return {"secrets": [{"name": name} for name in names]}
        if "/environments/" in path:
            return {"protection_rules": [{"type": "required_reviewers"}] if protected else []}
        return {}

    monkeypatch.setattr(cloud, "api", api)
    with pytest.raises(ValueError, match="required reviewers"):
        cloud.connection(project, "android", "deploy", "production", "vercel")
    protected = True
    with pytest.raises(ValueError, match="XWAV_GOOGLE_PLAY_JSON"):
        cloud.connection(project, "android", "deploy", "production", "vercel")
    names = cloud.required_secrets("android", "deploy", "vercel")
    assert (
        cloud.connection(project, "android", "deploy", "production", "vercel")[2]
        == "xwav-production"
    )
    assert "XWAV_APPLE_API_JSON" not in cloud.required_secrets("ios", "build", "vercel")


@pytest.mark.parametrize("filename", ["../escape", "nested/file", "\\escape", "/absolute"])
def test_cloud_artifact_archive_rejects_unsafe_paths(tmp_path, filename):
    with pytest.raises(ValueError, match="unsafe path"):
        cloud.unpack(bundle({filename: "bad"}), tmp_path)


def test_cloud_artifact_archive_rejects_symlink_and_duplicate(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        info = zipfile.ZipInfo("link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "../escape")
    with pytest.raises(ValueError, match="unsafe path"):
        cloud.unpack(buffer.getvalue(), tmp_path)
    (tmp_path / "web.zip").write_text("old")
    with pytest.raises(ValueError, match="duplicate"):
        cloud.unpack(bundle({"web.zip": "new"}), tmp_path)


@pytest.mark.parametrize(
    "fault", [None, "failure", "checksum", "wrong-commit", "cancel", "no-artifact"]
)
def test_dispatch_poll_download_integrity_and_cancellation(project, monkeypatch, fault):
    prepare(project)
    sha = commit(project)
    state = project.parent / "state"
    state.mkdir()
    run_id = "a" * 32
    selected = cloud.plan(project, "web", "build", "testing", "vercel")
    report = {
        "id": run_id,
        "workspace": str(project),
        "source_version": runtime.fingerprint(project),
        "state": "running",
        "checks": selected["steps"],
        "started_at": 0,
    }
    coordinator.save(state / f"{run_id}.json", report)
    web = bundle({"index.html": "<h1>Real package</h1>"})
    import hashlib

    manifest = {
        "commit": "wrong" if fault == "wrong-commit" else sha,
        "target": "web",
        "operation": "build",
        "channel": "testing",
        "artifacts": [
            {
                "name": "web.zip",
                "bytes": len(web),
                "sha256": "bad" if fault == "checksum" else hashlib.sha256(web).hexdigest(),
                "installable": False,
            }
        ],
    }
    archive = bundle({"manifest.json": json.dumps(manifest), "web.zip": web})
    calls = []

    def api(repo, path="", method="GET", data=None, binary=False):
        calls.append((repo, path, method, data, binary))
        if not path:
            return {"default_branch": "main"}
        if path.endswith("/dispatches"):
            assert data["ref"] == "main"
            assert data["inputs"]["source_sha"] == sha
            assert data["inputs"]["channel"] == "testing"
            if fault == "cancel":
                (state / f"{run_id}.cancel").touch()
            return {}
        if "?event=" in path:
            return {
                "workflow_runs": [
                    {"display_title": "xwav-" + run_id, "head_sha": "branch-moved", "id": 12}
                ]
            }
        if path.endswith("/runs/12"):
            return {
                "status": "completed",
                "conclusion": "failure" if fault == "failure" else "success",
            }
        if "/artifacts?" in path:
            return {
                "artifacts": []
                if fault == "no-artifact"
                else [{"id": 42, "name": "xwav-" + run_id}]
            }
        if binary:
            return archive
        return {}

    monkeypatch.setattr(cloud, "connection", lambda *_args: ("owner/app", sha, "xwav-build"))
    monkeypatch.setattr(cloud, "api", api)
    monkeypatch.setattr(cloud.time, "sleep", lambda _seconds: None)
    cloud.worker(state, run_id, coordinator.save, None, runtime.fingerprint, runtime)
    result = json.loads((state / f"{run_id}.json").read_text())
    assert result["state"] == (
        "complete" if fault is None else "cancelled" if fault == "cancel" else "error"
    ), result
    if fault is None:
        artifact = result["artifacts"][0]
        assert (project / artifact["path"]).read_bytes() == web
        assert result["source_commit"] == sha
        assert result["cloud_run_url"] == "https://github.com/owner/app/actions/runs/12"
    else:
        assert result["artifacts"] == []
        assert not (project / ".xwav/releases/artifacts" / run_id).exists()
    if fault == "cancel":
        assert any(path.endswith("/cancel") for _, path, *_ in calls)


@pytest.mark.parametrize("matching_source", [True, False])
def test_generated_cloud_worker_runs_real_web_build_without_xwav_install(project, matching_source):
    prepare(project)
    (project / "index.html").write_text("<h1>cloud smoke</h1>")
    sha = commit(project)
    env = {
        **os.environ,
        "GITHUB_SHA": sha,
        "XWAV_REQUEST": json.dumps(
            {
                "target": "web",
                "operation": "build",
                "channel": "testing",
                "source_sha": sha if matching_source else "0" * 40,
            }
        ),
    }
    result = subprocess.run(
        [sys.executable, ".xwav/cloud/entry.py"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if not matching_source:
        assert result.returncode != 0
        assert not (project / ".xwav/cloud-export").exists()
        return
    assert result.returncode == 0, (result.stdout, result.stderr)
    manifest = json.loads((project / ".xwav/cloud-export/manifest.json").read_text())
    assert manifest["commit"] == sha
    artifact = manifest["artifacts"][0]
    with zipfile.ZipFile(project / ".xwav/cloud-export" / artifact["name"]) as archive:
        assert archive.read("index.html") == b"<h1>cloud smoke</h1>"
    assert cloud.git(project, "status", "--porcelain") == ""


def test_api_never_forwards_token_to_artifact_storage(monkeypatch):
    import urllib.error
    import urllib.request

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    def redirect(request, **_kwargs):
        assert request.headers["Authorization"] == "Bearer private-test-token"
        raise urllib.error.HTTPError(
            request.full_url,
            302,
            "redirect",
            {"Location": "https://downloads.blob.core.windows.net/path?sig=abc"},
            None,
        )

    monkeypatch.setenv("GH_TOKEN", "private-test-token")
    monkeypatch.setattr(urllib.request, "build_opener", lambda *_args: Mock(open=redirect))
    requests = []
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda url, **_kwargs: requests.append(url) or Response(b"archive"),
    )
    assert cloud.api("owner/app", "/actions/artifacts/1/zip", binary=True) == b"archive"
    assert requests == ["https://downloads.blob.core.windows.net/path?sig=abc"]


@pytest.mark.parametrize(
    "target,channel",
    [("android", "testing"), ("android", "production"), ("ios", "testing"), ("ios", "production")],
)
def test_store_adapters_select_test_or_production_and_remove_credentials(
    tmp_path, monkeypatch, target, channel
):
    import runpy

    source = Path(cloud.__file__).parent / "release_templates/publish.py"
    publish = runpy.run_path(str(source))["publish"]
    state = tmp_path / ".xwav/cloud-state"
    state.mkdir(parents=True)
    package = "store.aab" if target == "android" else "store.ipa"
    (tmp_path / package).write_bytes(b"fixture package")
    (state / "run.json").write_text(
        json.dumps({"artifacts": [{"name": package, "path": package}]})
    )
    (tmp_path / ".xwav/release.json").write_text(json.dumps({"app_id": "com.example.test"}))
    monkeypatch.setenv("XWAV_GOOGLE_PLAY_JSON", '{"client_email":"test@example.test"}')
    monkeypatch.setenv("XWAV_APPLE_API_JSON", '{"key_id":"example"}')
    calls = []
    temporary_files = []

    def run(command, **_kwargs):
        calls.append(command)
        if command[0] == "fastlane":
            field = next(arg for arg in command if arg.startswith(("json_key:", "api_key_path:")))
            file = Path(field.split(":", 1)[1])
            temporary_files.append(file)
            assert json.loads(file.read_text())
            assert stat.S_IMODE(file.stat().st_mode) == 0o600
        return subprocess.CompletedProcess(command, 0, stdout="jar verified.", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    publish(tmp_path, target, channel)
    command = calls[-1]
    if target == "android":
        assert "track:" + ("internal" if channel == "testing" else "production") in command
    else:
        assert command[2] == (
            "upload_to_testflight" if channel == "testing" else "upload_to_app_store"
        )
        if channel == "production":
            assert "submit_for_review:false" in command
    assert temporary_files and all(not file.exists() for file in temporary_files)


def test_cloud_settings_and_workflow_changes_invalidate_packages(project):
    prepare(project)
    before = runtime.fingerprint(project)
    file = project / ".github/workflows/xwav-release.yml"
    file.write_text(file.read_text() + "\n# updated workflow\n")
    assert runtime.fingerprint(project) != before
    before = runtime.fingerprint(project)
    (project / ".xwav/cloud.json").write_text('{"repository":"other/app"}')
    assert runtime.fingerprint(project) != before

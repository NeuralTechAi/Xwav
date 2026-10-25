"""Workspace exports use sandbox reads and include working-tree changes."""

import zipfile

import httpx
import pytest
from fastapi import HTTPException

from omnigent.server import workspace_archive


@pytest.mark.parametrize("binary", [False, True])
async def test_archive_contains_uncommitted_and_untracked_files(binary):
    data = bytes(range(256)) * 100 if binary else b"uncommitted edits"
    requests = []

    def runner(request):
        requests.append(request)
        if request.url.params.get("download"):
            assert request.url.params["scope"] == "workspace"
            assert request.headers["accept-encoding"] == "identity"
            return httpx.Response(200, content=data, headers={"Content-Disposition": "attachment"})
        directory = request.url.path.split("filesystem/", 1)[1]
        entries = (
            [
                {"path": "src", "type": "directory"},
                {"path": ".git", "type": "directory"},
                {"path": "node_modules", "type": "directory"},
                {"path": "outside", "type": "symlink"},
            ]
            if not directory
            else [{"path": "src/new.txt", "type": "file"}]
        )
        return httpx.Response(200, json={"data": entries, "has_more": False})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(runner), base_url="http://runner"
    ) as client:
        archive = await workspace_archive.build_workspace_archive(client, "job-1")
    try:
        with zipfile.ZipFile(archive) as exported:
            assert exported.namelist() == ["src/", "src/new.txt"]
            assert exported.read("src/new.txt") == data
    finally:
        archive.close()
    assert len(requests) == 3


@pytest.mark.parametrize(
    "path",
    [
        "C:secret",
        "C:/secret",
        "../secret",
        "/etc/passwd",
        "src/../../secret",
        "a\\b",
        "a\x00b",
        "elsewhere/file",
    ],
)
async def test_archive_rejects_invalid_or_misparented_paths(path):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"path": path, "type": "file"}]})
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://runner") as client:
        with pytest.raises(HTTPException) as error:
            await workspace_archive.build_workspace_archive(client, "job")
    assert error.value.status_code == 502


@pytest.mark.parametrize("failure", ["size", "entries", "unreadable", "legacy", "cursor"])
async def test_archive_never_returns_a_silently_partial_zip(monkeypatch, failure):
    monkeypatch.setattr(workspace_archive, "MAX_EXPORT_BYTES", 1 if failure == "size" else 100)
    monkeypatch.setattr(
        workspace_archive, "MAX_EXPORT_ENTRIES", 0 if failure == "entries" else 100
    )

    def runner(request):
        if request.url.params.get("download"):
            return httpx.Response(
                403 if failure == "unreadable" else 200,
                content=b"file",
                headers={} if failure == "legacy" else {"Content-Disposition": "attachment"},
            )
        return httpx.Response(
            200,
            json={
                "data": [{"path": "app.txt", "type": "file"}],
                "has_more": failure == "cursor",
                "last_id": None,
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(runner), base_url="http://runner"
    ) as client:
        with pytest.raises(HTTPException) as error:
            await workspace_archive.build_workspace_archive(client, "job")
    assert error.value.status_code == (
        413 if failure in {"size", "entries"} else 502 if failure == "cursor" else 409
    )


async def test_archive_reads_all_directory_pages():
    def runner(request):
        if request.url.params.get("download"):
            return httpx.Response(
                200, content=b"saved", headers={"Content-Disposition": "attachment"}
            )
        more = not request.url.params.get("after")
        return httpx.Response(
            200,
            json={
                "data": [{"path": "first.txt" if more else "second.txt", "type": "file"}],
                "has_more": more,
                "last_id": "first.txt",
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(runner), base_url="http://runner"
    ) as client:
        archive = await workspace_archive.build_workspace_archive(client, "job")
    with archive, zipfile.ZipFile(archive) as exported:
        assert exported.namelist() == ["first.txt", "second.txt"]


async def test_archive_uses_selected_workspace_instead_of_runner_launch_directory():
    seen = []

    def runner(request):
        path = request.url.path.split("filesystem/", 1)[1]
        seen.append(path)
        if request.url.params.get("download"):
            assert path == "/selected/job/src/app.txt"
            return httpx.Response(
                200, content=b"job source", headers={"Content-Disposition": "attachment"}
            )
        entries = (
            [{"name": "src", "path": "/selected/job/src", "type": "directory"}]
            if path == "/selected/job"
            else [{"name": "app.txt", "path": "/selected/job/src/app.txt", "type": "file"}]
        )
        return httpx.Response(200, json={"data": entries})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(runner), base_url="http://runner"
    ) as client:
        archive = await workspace_archive.build_workspace_archive(
            client, "job", workspace="/selected/job"
        )
    try:
        with zipfile.ZipFile(archive) as exported:
            assert exported.namelist() == ["src/", "src/app.txt"]
            assert exported.read("src/app.txt") == b"job source"
    finally:
        archive.close()
    assert seen == ["/selected/job", "/selected/job/src", "/selected/job/src/app.txt"]


async def test_source_zip_preserves_release_settings_but_omits_generated_builds():
    seen = []

    def runner(request):
        path = request.url.path.split("filesystem/", 1)[1]
        seen.append(path)
        if request.url.params.get("download"):
            assert path == ".xwav/release.json"
            return httpx.Response(
                200,
                content=b'{"app_version":"2.3.4"}',
                headers={"Content-Disposition": "attachment"},
            )
        entries = (
            [{"path": ".xwav", "type": "directory"}]
            if not path
            else [
                {"path": ".xwav/release.json", "type": "file"},
                {"path": ".xwav/releases", "type": "directory"},
            ]
        )
        return httpx.Response(200, json={"data": entries})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(runner), base_url="http://runner"
    ) as client:
        archive = await workspace_archive.build_workspace_archive(client, "job")
    with archive, zipfile.ZipFile(archive) as exported:
        assert exported.namelist() == [".xwav/", ".xwav/release.json"]
        assert b"2.3.4" in exported.read(".xwav/release.json")
    assert ".xwav/releases" not in seen

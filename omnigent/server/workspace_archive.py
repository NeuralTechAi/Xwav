"""Bounded workspace ZIP exports using the runner's existing filesystem API."""

from __future__ import annotations

import tempfile
import zipfile
from collections import deque
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, BinaryIO
from urllib.parse import quote

from fastapi import HTTPException

MAX_EXPORT_BYTES = 512 * 1024 * 1024
MAX_EXPORT_ENTRIES = 20_000
EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
)


def _archive_path(path: object) -> str:
    if not isinstance(path, str) or not path or "\\" in path or "\0" in path:
        raise HTTPException(502, "The workspace returned an invalid file path.")
    if PureWindowsPath(path).drive:
        raise HTTPException(502, "The workspace returned an invalid file path.")
    parts = path.split("/")
    if path.startswith("/") or any(part in {"", ".", ".."} for part in parts):
        raise HTTPException(502, "The workspace returned an invalid file path.")
    return PurePosixPath(path).as_posix()


async def build_workspace_archive(
    client: Any,
    session_id: str,
    *,
    workspace: str | None = None,
    excluded_directories: frozenset[str] = frozenset(),
) -> BinaryIO:
    """Export saved working files, including uncommitted and untracked files.

    Every read goes through the existing sandbox filesystem boundary. Dependency
    caches, Git internals, symlinks and special files are omitted. Failed reads
    discard the export rather than returning a silently incomplete archive.
    """
    base = f"/v1/sessions/{quote(session_id, safe='')}/resources/environments/default/filesystem/"
    # A host runner may serve multiple jobs from a different launch directory.
    # Use the authorized conversation's selected workspace, never its process cwd.
    root = PurePosixPath(workspace) if workspace and workspace.startswith("/") else None

    def runner_path(path: str) -> str:
        return str(root / path) if root is not None else path

    output = tempfile.TemporaryFile(mode="w+b")  # noqa: SIM115 — response owns the open file
    directories = deque([""])
    seen: set[str] = set()
    total = 0
    try:
        with zipfile.ZipFile(
            output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=3
        ) as archive:
            while directories:
                directory = directories.popleft()
                cursor = None
                while True:
                    params = {"limit": "1000", "order": "asc"}
                    if cursor:
                        params["after"] = cursor
                    response = await client.get(
                        base + quote(runner_path(directory), safe="/"), params=params
                    )
                    if response.status_code != 200:
                        raise HTTPException(
                            503, "Job workspace is unavailable. Resume the job and retry."
                        )
                    listing = response.json()
                    if not isinstance(listing, dict) or not isinstance(listing.get("data"), list):
                        raise HTTPException(502, "The job returned an invalid workspace listing.")
                    for entry in listing["data"]:
                        if not isinstance(entry, dict):
                            raise HTTPException(
                                502, "The job returned an invalid workspace entry."
                            )
                        if root is not None:
                            # Build paths from the requested directory, rather than
                            # trusting runner-root-relative entry paths.
                            name = _archive_path(entry.get("name"))
                            if "/" in name:
                                raise HTTPException(502, "The job returned an invalid file name.")
                            path = str(PurePosixPath(directory) / name)
                        else:
                            path = _archive_path(entry.get("path"))
                        if PurePosixPath(path).parent.as_posix() != (directory or "."):
                            raise HTTPException(
                                502, "The job returned a file outside the requested directory."
                            )
                        if path in seen:
                            continue
                        seen.add(path)
                        if len(seen) > MAX_EXPORT_ENTRIES:
                            raise HTTPException(
                                413,
                                "Project export exceeds 20,000 entries. "
                                "Download a smaller project.",
                            )
                        if PurePosixPath(path).name == ".git":
                            continue
                        kind = entry.get("type")
                        if kind == "directory":
                            if (
                                PurePosixPath(path).name
                                not in EXCLUDED_DIRECTORIES | excluded_directories
                                and path != ".xwav/releases"
                            ):
                                directories.append(path)
                                archive.writestr(path + "/", b"")
                        elif kind == "file":
                            request = client.build_request(
                                "GET",
                                base + quote(runner_path(path), safe="/"),
                                params={"download": "true", "scope": "workspace"},
                                headers={"Accept-Encoding": "identity"},
                            )
                            stream = await client.send(request, stream=True)
                            try:
                                if (
                                    stream.status_code != 200
                                    or "content-disposition" not in stream.headers
                                ):
                                    raise HTTPException(
                                        409,
                                        "A project file cannot be read or changed during export. "
                                        "Retry the download.",
                                    )
                                header = stream.headers.get("content-length", "")
                                expected = int(header) if header.isdigit() else None
                                if expected is not None and total + expected > MAX_EXPORT_BYTES:
                                    raise HTTPException(
                                        413, "Project export exceeds 512 MiB of files."
                                    )
                                copied = 0
                                with archive.open(path, "w", force_zip64=True) as destination:
                                    async for chunk in stream.aiter_bytes(64 * 1024):
                                        total += len(chunk)
                                        copied += len(chunk)
                                        if total > MAX_EXPORT_BYTES:
                                            raise HTTPException(
                                                413, "Project export exceeds 512 MiB of files."
                                            )
                                        destination.write(chunk)
                                if expected is not None and copied != expected:
                                    raise HTTPException(
                                        409,
                                        "A project file changed during export. "
                                        "Retry the download.",
                                    )
                            finally:
                                await stream.aclose()
                    if not listing.get("has_more"):
                        break
                    next_cursor = listing.get("last_id")
                    if (
                        not isinstance(next_cursor, str)
                        or not next_cursor
                        or next_cursor == cursor
                    ):
                        raise HTTPException(502, "The job returned an invalid workspace cursor.")
                    cursor = next_cursor
        output.seek(0)
        return output
    except BaseException:
        output.close()
        raise

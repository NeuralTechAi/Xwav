"""Private, content-addressed file checkpoints; executable on existing job runners."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
import tempfile
import uuid
from pathlib import Path
from typing import Any

EXCLUDED = {".git", ".omnigent", ".venv", "venv", "node_modules", "__pycache__", ".cache", ".next"}
MAX_BYTES = 100 * 1024 * 1024
MAX_FILES = 10000


def _write(path: Path, content: bytes, mode: int = 0o600) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            os.fchmod(handle.fileno(), mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _scan(root: Path, blobs: Path) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    total = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        current = Path(directory)
        dirs[:] = sorted(name for name in dirs if name not in EXCLUDED)
        for name in [*dirs, *sorted(files)]:
            if name in EXCLUDED:
                continue
            path = current / name
            info = path.lstat()
            relative = path.relative_to(root).as_posix()
            entry: dict[str, Any] = {"mode": stat.S_IMODE(info.st_mode)}
            if path.is_symlink():
                entry.update(type="link", target=os.readlink(path))
            elif path.is_dir():
                entry.update(type="directory")
            elif path.is_file():
                total += info.st_size
                if total > MAX_BYTES:
                    raise ValueError("Workspace exceeds the 100 MB checkpoint limit")
                content = path.read_bytes()
                digest = hashlib.sha256(content).hexdigest()
                blob = blobs / digest
                if not blob.exists():
                    _write(blob, content)
                entry.update(type="file", blob=digest)
            else:
                raise ValueError("Workspace contains unsupported special files")
            entries[relative] = entry
            if len(entries) > MAX_FILES:
                raise ValueError("Workspace exceeds the 10,000-entry checkpoint limit")
    return entries


def _fingerprint(entries: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()


def _manifest_path(storage: Path, anchor: str) -> Path:
    return storage / (hashlib.sha256(anchor.encode()).hexdigest() + ".json")


def _load(storage: Path, anchor: str) -> dict[str, Any]:
    path = _manifest_path(storage, anchor)
    if not path.is_file():
        raise ValueError(
            "No file checkpoint was saved before this message. Older messages cannot be reverted."
        )
    manifest = json.loads(path.read_text())
    if manifest.get("anchor") != anchor:
        raise ValueError("Checkpoint does not match this message")
    return manifest


def _save(storage: Path, anchor: str, entries: dict[str, Any]) -> None:
    _write(
        _manifest_path(storage, anchor), json.dumps({"anchor": anchor, "files": entries}).encode()
    )


def _validate(root: Path, entries: dict[str, Any], blobs: Path) -> None:
    for name, entry in entries.items():
        relative = Path(name)
        if (
            relative.is_absolute()
            or not relative.parts
            or any(part in {"..", "."} or part in EXCLUDED for part in relative.parts)
        ):
            raise ValueError("Unsafe checkpoint path")
        if not (root / relative).is_relative_to(root):
            raise ValueError("Unsafe checkpoint path")
        if entry["type"] == "file":
            digest = entry["blob"]
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError("Invalid checkpoint file")
            content = (blobs / digest).read_bytes()
            if hashlib.sha256(content).hexdigest() != digest:
                raise ValueError("Checkpoint file is damaged; nothing was restored")


def _restore(root: Path, saved: dict[str, Any], current: dict[str, Any], blobs: Path) -> None:
    # Refuse a file/directory replacement that would remove excluded dependencies.
    for name, entry in current.items():
        target = saved.get(name)
        if entry["type"] == "directory" and target and target["type"] != "directory":
            if any(child.name in EXCLUDED for child in (root / name).rglob("*")):
                raise ValueError("A dependency directory blocks restoration; nothing was restored")
    for name in sorted(current, key=lambda value: (-len(Path(value).parts), value)):
        entry = current[name]
        target = saved.get(name)
        if target is not None and target["type"] == entry["type"]:
            continue
        path = root / name
        if entry["type"] == "directory":
            try:
                path.rmdir()
            except OSError:
                if target is not None:
                    raise
        else:
            path.unlink()
    for name in sorted(saved, key=lambda value: (len(Path(value).parts), value)):
        entry = saved[name]
        path = root / name
        if any(parent.is_symlink() for parent in path.parents if parent != root):
            raise ValueError("A symbolic link blocks safe restoration")
        if entry["type"] == "directory":
            path.mkdir(exist_ok=True)
            path.chmod(entry["mode"] | 0o700)
        elif entry["type"] == "link":
            if path.is_symlink():
                path.unlink()
            path.symlink_to(entry["target"])
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            _write(path, (blobs / entry["blob"]).read_bytes(), entry["mode"])
    for name in sorted(saved, key=lambda value: -len(Path(value).parts)):
        if saved[name]["type"] == "directory":
            (root / name).chmod(saved[name]["mode"])


def checkpoint_request(request: dict[str, Any]) -> dict[str, Any]:
    """Capture, review or restore files; callers authorize the session and require idle work."""
    root = Path(request.get("workspace") or Path.cwd()).expanduser().resolve()
    if root == Path(root.anchor) or root == Path.home():
        return {"state": "unavailable", "message": "Select a project workspace first"}
    key = hashlib.sha256(f"{request['session_id']}:{root}".encode()).hexdigest()
    storage = Path(request.get("storage_root") or Path.home() / ".omnigent" / "checkpoints") / key
    storage.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(storage, 0o700)
    blobs = storage / "blobs"
    blobs.mkdir(mode=0o700, exist_ok=True)
    anchor = request["anchor"]
    try:
        with (storage / "lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if request["action"] == "capture":
                if not _manifest_path(storage, anchor).exists():
                    _save(storage, anchor, _scan(root, blobs))
                return {"state": "ready"}
            saved = _load(storage, anchor)["files"]
            _validate(root, saved, blobs)
            current = _scan(root, blobs)
            changes = [
                {"path": name, "action": "restore" if name in saved else "remove"}
                for name in sorted(set(saved) | set(current))
                if saved.get(name) != current.get(name)
            ]
            token = _fingerprint(current)
            if request["action"] == "plan":
                return {
                    "state": "ready",
                    "token": token,
                    "changes": changes[:200],
                    "count": len(changes),
                }
            if request["action"] != "apply" or request.get("token") != token:
                return {
                    "state": "conflict",
                    "message": "Files changed. Review the revert again before restoring.",
                }
            backup = "undo_" + uuid.uuid4().hex
            _save(storage, backup, current)
            try:
                _restore(root, saved, current, blobs)
            except (OSError, ValueError):
                # Keep both checkpoints even when rollback itself cannot complete.
                _restore(root, current, _scan(root, blobs), blobs)
                raise
            return {"state": "restored", "count": len(changes), "backup_id": backup}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {"state": "unavailable", "message": str(error)}

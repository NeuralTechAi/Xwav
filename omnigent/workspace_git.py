"""Small, transportable Git actions for the job's own repository."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


def git_request(request: dict) -> dict:
    """Review status, stage workspace changes, or commit the reviewed index."""
    root = Path(request.get("workspace") or Path.cwd()).expanduser().resolve()

    def git(*args: str, check: bool = True) -> bytes:
        result = subprocess.run(
            ["git", "--literal-pathspecs", "-C", str(root), *args],
            capture_output=True,
            timeout=60,
        )
        if check and result.returncode:
            raise ValueError(result.stderr.decode(errors="replace")[:4000] or "Git failed")
        return result.stdout if result.returncode == 0 else b""

    def status() -> dict:
        records = git("status", "--porcelain=v1", "-z", "--untracked-files=all").split(b"\0")
        files = []
        index = 0
        while index < len(records):
            record = records[index]
            index += 1
            if not record:
                continue
            code = record[:2].decode("ascii")
            path = record[3:].decode(errors="replace")
            if "R" in code or "C" in code:
                index += 1  # porcelain -z has a second path for rename/copy sources
            files.append(
                {"path": path, "staged": code[0] not in {" ", "?"}, "unstaged": code[1] != " "}
            )
        head = git("rev-parse", "--verify", "HEAD", check=False)
        index_state = git("diff", "--cached", "--raw", "--no-abbrev", "-z")
        branch = (
            git("symbolic-ref", "--short", "HEAD", check=False).decode().strip() or "Detached HEAD"
        )
        return {
            "state": "ready",
            "branch": branch,
            "repository": str(root),
            "files": files[:500],
            "count": len(files),
            "staged_count": sum(1 for file in files if file["staged"]),
            "unstaged_count": sum(1 for file in files if file["unstaged"]),
            "author_required": not bool(
                git("var", "GIT_AUTHOR_IDENT", check=False)
                and git("var", "GIT_COMMITTER_IDENT", check=False)
            ),
            "token": hashlib.sha256(head + index_state + branch.encode()).hexdigest(),
        }

    try:
        if not root.is_dir():
            raise ValueError("Select a project workspace first")
        action = request.get("action")
        if action not in ("status", "stage", "commit", "init"):
            raise ValueError("Choose status, init, stage or commit")
        repo = git("rev-parse", "--show-toplevel", check=False).decode().strip()
        if not repo:
            if any(
                (parent / ".git").is_file() or (parent / ".git" / "HEAD").is_file()
                for parent in (root, *root.parents)
            ):
                raise ValueError(
                    "An existing Git repository could not be accessed. "
                    "Check its permissions and ownership"
                )
            if action == "init":
                git("init")
                # Only new repositories receive local dependency/secret exclusions.
                exclude = root / ".git" / "info" / "exclude"
                with exclude.open("a") as output:
                    output.write(
                        "\n# Xwav local build and runtime files\nnode_modules/\n.venv/\n"
                        "__pycache__/\n.xwav/\n.omnigent/\n.env\n.env.*\n!.env.example\n"
                    )
                repo = str(root)
            elif action == "status":
                return {
                    "state": "not_git",
                    "files": [],
                    "count": 0,
                    "staged_count": 0,
                    "unstaged_count": 0,
                    "repository": str(root),
                }
            else:
                raise ValueError("Initialize a Git repository before staging or committing")
        if Path(repo).resolve() != root:
            raise ValueError(
                "Open this job at the Git repository root to stage or commit its files"
            )
        current = status()
        if action == "stage":
            if not current["unstaged_count"]:
                raise ValueError("There are no unstaged changes")
            git("add", "-A", "--", ".")
        elif action == "commit":
            message = request.get("message")
            if (
                not isinstance(message, str)
                or not message.strip()
                or len(message) > 4000
                or "\0" in message
            ):
                raise ValueError("Enter a commit message of 1–4,000 characters")
            if not request.get("token") or request["token"] != current["token"]:
                raise ValueError(
                    "Staged files or HEAD changed. Refresh and review them before committing"
                )
            if not current["staged_count"]:
                raise ValueError("Stage changes before creating a commit")
            author_options: list[str] = []
            if current["author_required"]:
                name, email = request.get("author_name"), request.get("author_email")
                if (
                    not isinstance(name, str)
                    or not name.strip()
                    or len(name) > 200
                    or not isinstance(email, str)
                    or "@" not in email
                    or len(email) > 200
                    or any(char in name + email for char in "\n\r\0<>")
                ):
                    raise ValueError("Enter the author name and email for this commit")
                author_options = [
                    "-c",
                    f"user.name={name.strip()}",
                    "-c",
                    f"user.email={email.strip()}",
                ]
            git(*author_options, "commit", "-m", message.strip())
        result = status() if action != "status" else current
        if action == "commit":
            result.update(state="committed", commit=git("rev-parse", "HEAD").decode().strip())
        elif action == "stage":
            result["state"] = "staged"
        return result
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return {"state": "unavailable", "message": str(exc)[:4000]}


def git_command(workspace: str | None, body: dict) -> str:
    """Ship this stdlib-only implementation to older job runners without installs."""
    parameters = {
        key: body.get(key) for key in ("action", "message", "token", "author_name", "author_email")
    }
    parameters["workspace"] = workspace
    return (
        "python3 - <<'XWAV_GIT_ACTION'\n"
        + Path(__file__).read_text()
        + "\nprint(json.dumps(git_request(json.loads("
        + repr(json.dumps(parameters))
        + "))))\nXWAV_GIT_ACTION"
    )

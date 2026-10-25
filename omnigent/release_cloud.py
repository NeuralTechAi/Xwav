"""Lightweight GitHub Actions orchestration; credentials remain in the job environment."""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

WORKFLOW = "xwav-release.yml"
LIMIT = 512 * 1024 * 1024


def settings(root):
    file = root / ".xwav/cloud.json"
    cfg = json.loads(file.read_text()) if file.is_file() else {}
    if not isinstance(cfg, dict):
        raise ValueError("Cloud settings must be an object")
    repo = cfg.get("repository", "")
    if (
        not isinstance(repo, str)
        or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)
        or ".." in repo
    ):
        raise ValueError("Set a GitHub repository as owner/repository")
    return cfg


def token():
    credential = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not credential and shutil.which("gh"):
        result = subprocess.run(
            ["gh", "auth", "token", "--hostname", "github.com"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            credential = result.stdout.strip()
    if not credential:
        raise ValueError(
            "Connect GitHub in this job: gh auth login, or a scoped GH_TOKEN with "
            "Contents read and Actions write. Environment checks also need "
            "Environments read and environment Secrets read."
        )
    return credential


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        del req, fp, code, msg, headers, newurl
        return


def api(repository, path="", method="GET", data=None, binary=False):
    if not path.startswith("/") and path:
        raise ValueError("Invalid GitHub API path")
    url = "https://api.github.com/repos/" + repository + path
    payload = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(
        url,
        data=payload,
        method=method,
        headers={
            "Authorization": "Bearer " + token(),
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Xwav-Release",
        },
    )
    try:
        response = urllib.request.build_opener(NoRedirect).open(request, timeout=30)
    except urllib.error.HTTPError as error:
        if binary and error.code in {301, 302, 303, 307}:
            location = error.headers.get("Location", "")
            parsed = urllib.parse.urlsplit(location)
            if parsed.scheme != "https" or not (parsed.hostname or "").endswith(
                (".githubusercontent.com", ".blob.core.windows.net")
            ):
                raise ValueError("Unexpected GitHub artifact download host") from None
            # Signed artifact URL deliberately receives no GitHub Authorization header.
            response = urllib.request.urlopen(location, timeout=60)
        else:
            raise ValueError(
                f"GitHub returned HTTP {error.code}. Check repository, workflow, "
                "environment and token permissions."
            ) from None
    with response:
        body = response.read(LIMIT + 1 if binary else 2 * 1024 * 1024)
    if binary:
        if len(body) > LIMIT:
            raise ValueError("Cloud package exceeds 512 MiB")
        return body
    return json.loads(body) if body else {}


def git(root, *args):
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, timeout=10
    )
    if result.returncode:
        raise ValueError("Cloud builds require a committed Git repository in the project folder")
    return result.stdout.strip()


def preflight(root, _target, operation, channel, _provider):
    cfg = settings(root)
    repository = cfg["repository"]
    token()
    if not (root / ".github/workflows" / WORKFLOW).is_file():
        raise ValueError(
            "Prepare the cloud workflow, commit it and push it to GitHub's default branch first"
        )
    if git(root, "rev-parse", "--show-prefix"):
        raise ValueError(
            "Cloud releases currently require the project folder to be the repository root"
        )
    if git(root, "status", "--porcelain", "--untracked-files=normal"):
        raise ValueError("Commit and push saved project changes before a cloud release")
    try:
        git(
            root,
            "ls-files",
            "--error-unmatch",
            ".github/workflows/" + WORKFLOW,
            ".xwav/cloud.json",
            ".xwav/cloud/entry.py",
            ".xwav/cloud/publish.py",
            ".xwav/cloud/release_runtime.py",
            ".xwav/cloud/release_tools.py",
            ".xwav/cloud/coordinator.py",
        )
    except ValueError as error:
        raise ValueError(
            "Commit the generated cloud files; force-add .xwav/cloud "
            "and .xwav/cloud.json if ignored by your repository"
        ) from error
    sha = git(root, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40,64}", sha):
        raise ValueError("Invalid source commit")
    environment = "xwav-build" if operation == "build" else "xwav-" + channel
    return repository, sha, environment


def required_secrets(target, operation, provider):
    names = []
    if target == "ios":
        names += [
            "XWAV_IOS_CERTIFICATE_B64",
            "XWAV_IOS_CERTIFICATE_PASSWORD",
            "XWAV_IOS_PROFILE_B64",
            "XWAV_IOS_EXPORT_OPTIONS_B64",
        ]
    if operation == "deploy":
        if target == "android":
            names += [
                "XWAV_ANDROID_KEYSTORE_B64",
                "XWAV_ANDROID_KEYSTORE_PASSWORD",
                "XWAV_ANDROID_KEY_ALIAS",
                "XWAV_ANDROID_KEY_PASSWORD",
                "XWAV_GOOGLE_PLAY_JSON",
            ]
        elif target == "ios":
            names += ["XWAV_APPLE_API_JSON"]
        elif target == "web":
            names += {
                "vercel": ["VERCEL_TOKEN"],
                "netlify": ["NETLIFY_AUTH_TOKEN"],
                "cloudflare": ["CLOUDFLARE_API_TOKEN"],
                "railway": ["RAILWAY_TOKEN"],
                "project": [],
            }[provider]
    return names


def connection(root, target, operation, channel, provider):
    repository, sha, environment = preflight(root, target, operation, channel, provider)
    api(repository, "/commits/" + sha)
    workflow = api(repository, "/actions/workflows/" + WORKFLOW)
    if workflow.get("state") != "active":
        raise ValueError("Enable the Xwav release workflow in GitHub Actions")
    env = api(repository, "/environments/" + environment)
    if (
        operation == "deploy"
        and channel == "production"
        and not any(
            row.get("type") == "required_reviewers" for row in env.get("protection_rules", [])
        )
    ):
        raise ValueError(
            "Add required reviewers to the xwav-production environment "
            "before production publishing"
        )
    present = {
        row["name"]
        for row in api(repository, "/environments/" + environment + "/secrets?per_page=100").get(
            "secrets", []
        )
    }
    missing = set(required_secrets(target, operation, provider)) - present
    if missing:
        raise ValueError(
            "Add environment secrets to " + environment + ": " + ", ".join(sorted(missing))
        )
    return repository, sha, environment


def plan(root, target, operation, channel, provider, verify=False):
    reason = ""
    try:
        (connection if verify else preflight)(root, target, operation, channel, provider)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        reason = str(error)
    return {
        "target": target,
        "ready": not reason,
        "reason": reason,
        "setup": "Cloud worker builds the exact committed revision. "
        "SDKs and signing stay on the worker.",
        "android_licenses_required": target == "android",
        "steps": [
            {
                "id": "release",
                "name": f"Cloud {operation} {target}",
                "platform": target,
                "category": "release",
                "status": "queued",
                "target": target,
                "operation": operation,
                "provider": provider,
                "site": "",
                "channel": channel,
                "engine": "github",
            }
        ],
    }


def prepare(root, repository, files):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or ".." in repository:
        raise ValueError("Enter owner/repository, without a URL or token")
    git(root, "rev-parse", "--show-toplevel")
    if git(root, "rev-parse", "--show-prefix"):
        raise ValueError("Select the Git repository root as the project folder")
    ignore = root / ".gitignore"
    if ignore.is_symlink() or not ignore.resolve().is_relative_to(root.resolve()):
        raise ValueError("The project gitignore must not be a symlink")
    pending = {**files, ".xwav/cloud.json": json.dumps({"repository": repository}, indent=2)}
    # Refuse existing user-owned workflows; repeated identical setup is safe.
    for path, source in pending.items():
        destination = root / path
        if destination.is_symlink() or not destination.resolve().is_relative_to(root.resolve()):
            raise ValueError("Cloud setup paths must stay inside the project")
        if destination.exists() and destination.read_text() != source:
            raise ValueError(
                "Cloud setup would replace " + path + ". Review or remove that file first."
            )
    for path, source in pending.items():
        destination = root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source)
    ignore = root / ".gitignore"
    text = ignore.read_text() if ignore.exists() else ""
    for pattern in [
        "/.xwav/releases/",
        "/.xwav/cloud-export/",
        "/.xwav/cloud-state/",
        "/.xwav/ExportOptions.plist",
    ]:
        if pattern not in text.splitlines():
            text += "\n" + pattern + "\n"
    ignore.write_text(text)
    return (
        "Cloud workflow prepared. Review, commit and push these files to the "
        "default branch; configure GitHub environments and secrets, then check connection."
    )


def unpack(payload, destination):
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        infos = archive.infolist()
        if len(infos) > 22 or sum(row.file_size for row in infos) > LIMIT:
            raise ValueError("Cloud artifacts exceed package limits")
        for row in infos:
            if row.is_dir():
                continue
            if (
                Path(row.filename).name != row.filename
                or "\\" in row.filename
                or stat.S_ISLNK(row.external_attr >> 16)
            ):
                raise ValueError("Cloud artifact archive contains an unsafe path")
            file = destination / row.filename
            if file.exists():
                raise ValueError("Cloud artifact archive contains duplicate names")
            file.write_bytes(archive.read(row))


def worker(directory, run_id, save, _execute, fingerprint, runtime):
    file = directory / f"{run_id}.json"
    report = json.loads(file.read_text())
    root = Path(report["workspace"])
    check = report["checks"][0]
    cancel = directory / f"{run_id}.cancel"
    output = root / ".xwav/releases/artifacts" / run_id
    remote_id = None
    repository = None
    report["worker_pid"] = os.getpid()
    save(file, report)
    started = time.monotonic()
    try:
        if cancel.exists():
            raise RuntimeError("Cancelled before dispatch")
        repository, sha, _environment = connection(
            root, check["target"], check["operation"], check["channel"], check["provider"]
        )
        if check["target"] == "android" and not check.get("accept_android_licenses"):
            raise ValueError("Accept Android SDK licences before dispatch")
        check.update(status="running", phase="Starting GitHub Actions")
        save(file, report)
        report["cloud_run_url"] = f"https://github.com/{repository}/actions/workflows/{WORKFLOW}"
        save(file, report)
        default_branch = api(repository)["default_branch"]
        api(
            repository,
            "/actions/workflows/" + WORKFLOW + "/dispatches",
            "POST",
            {
                "ref": default_branch,
                "inputs": {
                    "source_sha": sha,
                    "request_id": run_id,
                    "target": check["target"],
                    "operation": check["operation"],
                    "channel": check["channel"],
                    "provider": check["provider"],
                    "site": check.get("site", ""),
                    "accept_android_licenses": "true"
                    if check.get("accept_android_licenses")
                    else "false",
                },
            },
        )
        while time.monotonic() - started < 2700:
            if remote_id is None:
                runs = api(
                    repository,
                    "/actions/workflows/"
                    + WORKFLOW
                    + "/runs?event=workflow_dispatch&per_page=100",
                ).get("workflow_runs", [])
                matches = [row for row in runs if row.get("display_title") == "xwav-" + run_id]
                if matches:
                    remote_id = int(matches[0]["id"])
                    report["cloud_run_url"] = (
                        f"https://github.com/{repository}/actions/runs/{remote_id}"
                    )
                    report["source_commit"] = sha
                    save(file, report)
            if cancel.exists():
                # Continue finding the dispatch briefly so cancellation cannot silently orphan it.
                if remote_id:
                    api(repository, f"/actions/runs/{remote_id}/cancel", "POST")
                    raise RuntimeError("Cancelled; GitHub cancellation requested")
            if remote_id:
                state = api(repository, f"/actions/runs/{remote_id}")
                check["phase"] = "GitHub: " + state.get("status", "queued")
                save(file, report)
                if state.get("status") == "completed":
                    if state.get("conclusion") != "success":
                        raise ValueError(
                            "GitHub build "
                            + str(state.get("conclusion"))
                            + ". Open worker logs for details."
                        )
                    break
            time.sleep(3)
        else:
            raise RuntimeError("Cloud build timed out; inspect the linked workflow")
        if cancel.exists():
            raise RuntimeError("Cancelled")
        bundles = api(repository, f"/actions/runs/{remote_id}/artifacts?per_page=100").get(
            "artifacts", []
        )
        matching = [
            row
            for row in bundles
            if row.get("name") == "xwav-" + run_id and not row.get("expired")
        ]
        if len(matching) != 1:
            raise ValueError("The cloud worker did not return its release bundle")
        output.mkdir(parents=True, exist_ok=True)
        unpack(
            api(repository, f"/actions/artifacts/{int(matching[0]['id'])}/zip", binary=True),
            output,
        )
        manifest = json.loads((output / "manifest.json").read_text())
        if any(
            manifest.get(key) != value
            for key, value in {
                "commit": sha,
                "target": check["target"],
                "operation": check["operation"],
                "channel": check["channel"],
            }.items()
        ):
            raise ValueError("Cloud package does not match the requested source and destination")
        artifacts = []
        for row in manifest.get("artifacts", []):
            name = row["name"]
            if Path(name).name != name or name == "manifest.json":
                raise ValueError("Invalid cloud package name")
            package = output / name
            if (
                not runtime.artifact_valid(package, check["target"])
                or package.stat().st_size != row["bytes"]
                or runtime.file_digest(package) != row["sha256"]
            ):
                raise ValueError("Cloud package checksum or format validation failed")
            artifacts.append({**row, "path": str(package.relative_to(root))})
        if not artifacts and check["operation"] == "build":
            raise ValueError("Cloud build returned no downloadable package")
        if fingerprint(root) != report["source_version"]:
            raise ValueError(
                "Project changed during cloud build. Build the updated revision again."
            )
        report.update(
            state="complete",
            artifacts=artifacts,
            urls=[
                url
                for url in manifest.get("urls", [])
                if isinstance(url, str)
                and re.fullmatch(r"https://[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_./?=-]*)?", url)
            ],
        )
        check.update(
            status="passed",
            phase="Build ready"
            if check["operation"] == "build"
            else "Uploaded to " + check["channel"],
        )
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        RuntimeError,
        subprocess.SubprocessError,
        zipfile.BadZipFile,
    ) as error:
        if remote_id and repository:
            with contextlib.suppress(OSError, ValueError):
                api(repository, f"/actions/runs/{remote_id}/cancel", "POST")
        report.update(
            state="cancelled" if cancel.exists() else "error",
            artifacts=[],
            error=runtime.redact(str(error)),
        )
        check.update(status="cancelled" if cancel.exists() else "failed", reason=report["error"])
        shutil.rmtree(output, ignore_errors=True)
    try:
        changed = fingerprint(root) != report["source_version"]
    except (OSError, ValueError, TypeError, KeyError):
        changed = True
    report.update(finished_at=time.time(), source_changed=changed)
    check["duration"] = round(time.monotonic() - started, 2)
    save(file, report)


def request_action(options, coordinator, runtime, source):
    root = Path(options["workspace"] or Path.cwd()).expanduser().resolve()
    action = options["action"]
    target, operation, provider, channel = (
        options[key] for key in ("target", "operation", "provider", "channel")
    )
    selected = plan(root, target, operation, channel, provider)
    selected["steps"][0].update(
        site=options["site"], accept_android_licenses=options["accept_android_licenses"]
    )
    if action == "start" and not selected["ready"]:
        raise ValueError(selected["reason"])
    if action == "start" and target == "android" and not options["accept_android_licenses"]:
        raise ValueError("Accept Android SDK licences before starting")

    def version(path):
        try:
            return runtime.fingerprint(path)
        except (OSError, ValueError, TypeError, KeyError):
            return "unavailable"

    report = coordinator.request_action(
        {**options, "action": "status" if action == "verify" else action},
        source,
        "",
        kind="releases",
        discover_checks=lambda _root: selected["steps"],
        notice=runtime.NOTICE,
        source_fingerprint=version,
    )
    report["plans"] = [
        plan(
            root, item, operation, channel, provider, verify=action == "verify" and item == target
        )
        for item in runtime.TARGETS
    ]
    report["cloud"] = {"repository": ""}
    if (
        action == "verify"
        and next(item for item in report["plans"] if item["target"] == target)["ready"]
    ):
        report["cloud"]["message"] = (
            "Repository, workflow, environment and required secret names verified. "
            "Credential validity is checked by the build and publishing tools."
        )
    with contextlib.suppress(ValueError):
        report["cloud"]["repository"] = settings(root)["repository"]
    return report

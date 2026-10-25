"""On-demand app builds and deployment, executed inside the owning job runtime."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import plistlib
import re
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any

from omnigent import release_tools

TARGETS = ("web", "android", "ios", "windows")
PROVIDERS = ("vercel", "netlify", "cloudflare", "railway", "project")
NOTICE = (
    "Builds run in this job; tools are downloaded only when needed and reuse their caches. "
    "Mobile and desktop conversion packages a compatible browser frontend, not a server backend. "
    "API services must remain reachable. Native signing, store accounts and provider login are "
    "required where applicable. A store upload is a submission, not store approval."
)


def fingerprint(root: Path) -> str:
    """Track source and release settings while excluding generated/cache files."""
    ignored = {
        ".git",
        ".xwav",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        "dist",
        "build",
        "out",
        "www",
        "coverage",
        "Pods",
    }
    cfg = config(root)
    output = cfg.get("web_output")
    builds_web = bool(
        script(root, "build")
        or script(root, "build:web")
        or cfg.get("targets", {}).get("web", {}).get("build")
    )
    excluded = within(root, output) if builds_web and output and output != "." else None
    static_source = None
    if not builds_web:
        for value in [output] if output else ["dist", "build", "out", "www"]:
            candidate = within(root, value)
            if (candidate / "index.html").is_file():
                static_source = candidate
                break
    patterns = [
        pattern for row in cfg.get("targets", {}).values() for pattern in row.get("artifacts", [])
    ]
    generated = {
        root / "android/app/src/main/assets/public",
        root / "android/capacitor-cordova-android-plugins",
        root / "ios/App/App/public",
    }
    digest = hashlib.sha256()
    count = total_bytes = 0
    for parent, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(
            name
            for name in dirs
            if (
                (name not in ignored and not name.startswith("."))
                or (
                    static_source is not None
                    and (
                        Path(parent) / name == static_source
                        or Path(parent) / name in static_source.parents
                    )
                )
            )
            and not (Path(parent) / name).is_symlink()
            and (Path(parent) / name).resolve() != excluded
            and Path(parent) / name not in generated
        )
        for name in sorted(files):
            file = Path(parent) / name
            if (
                file.is_symlink()
                or any(file.relative_to(root).match(pattern) for pattern in patterns)
                or file.relative_to(root).as_posix()
                in {
                    "android/app/src/main/assets/capacitor.config.json",
                    "android/app/src/main/assets/capacitor.plugins.json",
                }
            ):
                continue
            info = file.stat()
            total_bytes += info.st_size
            if total_bytes > 256 * 1024 * 1024:
                raise ValueError("Project source exceeds the release limit of 256 MiB")
            digest.update(f"{file.relative_to(root)}:{info.st_size}:".encode())
            with file.open("rb") as stream:
                for chunk in iter(lambda: stream.read(65536), b""):
                    digest.update(chunk)
            count += 1
            if count >= 10000:
                raise ValueError("Project exceeds the release source limit of 10,000 files")
    settings_files = [
        root / ".xwav" / name for name in ("release.json", "ExportOptions.plist", "cloud.json")
    ]
    settings_files += [root / ".github/workflows/xwav-release.yml"]
    settings_files += sorted((root / ".xwav/cloud").glob("*.py"))
    for file in settings_files:
        if file.is_file() and not file.is_symlink() and file.resolve().is_relative_to(root):
            if file.stat().st_size > 1024 * 1024:
                raise ValueError("Release setup file exceeds 1 MiB")
            digest.update(str(file.relative_to(root)).encode())
            digest.update(file.read_bytes())
    return digest.hexdigest()


def within(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    if path != root and root not in path.parents:
        raise ValueError("Release paths must stay inside the project")
    return path


def config(root: Path) -> dict:
    file = root / ".xwav/release.json"
    data = json.loads(file.read_text()) if file.exists() else {}
    if not isinstance(data, dict) or not isinstance(data.get("targets", {}), dict):
        raise ValueError("Release configuration must be an object with a targets object")
    for target, row in data.get("targets", {}).items():
        if target not in TARGETS or not isinstance(row, dict):
            raise ValueError("Invalid release target")
        for key in ("build", "deploy"):
            command = row.get(key)
            if command is not None and (
                not isinstance(command, list)
                or not command
                or len(command) > 100
                or any(not isinstance(item, str) or not item or "\0" in item for item in command)
            ):
                raise ValueError("Build/deploy commands must be argument arrays")
        patterns = row.get("artifacts", [])
        if not isinstance(patterns, list) or len(patterns) > 20:
            raise ValueError("Choose at most 20 artifact patterns")
        for pattern in patterns:
            if (
                not isinstance(pattern, str)
                or not pattern
                or ".." in Path(pattern).parts
                or Path(pattern).is_absolute()
            ):
                raise ValueError("Artifact patterns must stay inside the project")
    if "build_number" in data and (
        not isinstance(data["build_number"], int)
        or isinstance(data["build_number"], bool)
        or not 1 <= data["build_number"] <= 2100000000
    ):
        raise ValueError("build_number must be an integer between 1 and 2100000000")
    if "app_id" in data and (
        not isinstance(data["app_id"], str)
        or not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z][A-Za-z0-9]*)+", data["app_id"])
    ):
        raise ValueError(
            "app_id must be a dotted application identifier such as com.example.myapp"
        )
    if "app_version" in data and (
        not isinstance(data["app_version"], str)
        or not re.fullmatch(
            r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?(?:\+[A-Za-z0-9.-]+)?", data["app_version"]
        )
    ):
        raise ValueError("app_version must be a semantic version such as 1.2.3")
    if data.get("web_output") is not None:
        if not isinstance(data["web_output"], str):
            raise ValueError("web_output must be a project-relative directory")
        within(root, data["web_output"])
    return data


def package(root: Path) -> dict:
    file = root / "package.json"
    data = json.loads(file.read_text()) if file.exists() else {}
    if not isinstance(data, dict) or not isinstance(data.get("scripts", {}), dict):
        raise ValueError("Invalid package.json")
    for key in ("dependencies", "devDependencies", "scripts"):
        mapping = data.get(key, {})
        if not isinstance(mapping, dict) or any(
            not isinstance(value, str) for value in mapping.values()
        ):
            raise ValueError(f"package.json {key} must map names to strings")
    return data


def package_manager(root: Path) -> str:
    declared = package(root).get("packageManager", "")
    if isinstance(declared, str) and re.fullmatch(
        r"(npm|pnpm|yarn|bun)@[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?", declared
    ):
        return declared
    for lock, manager in (
        ("pnpm-lock.yaml", "pnpm@10"),
        ("yarn.lock", "yarn@1.22.22"),
        ("bun.lock", "bun@1"),
        ("bun.lockb", "bun@1"),
    ):
        if (root / lock).exists():
            return manager
    return "npm"


def script(root: Path, name: str) -> list[str] | None:
    if name not in package(root).get("scripts", {}):
        return None
    return [package_manager(root).split("@")[0], "run", name]


def web_build(root: Path) -> list[str] | None:
    return (
        config(root).get("targets", {}).get("web", {}).get("build")
        or script(root, "build:web")
        or script(root, "build")
    )


def default_patterns(target: str) -> list[str]:
    return {
        "web": [],
        "android": ["android/app/build/outputs/**/*.apk", "android/app/build/outputs/**/*.aab"],
        "ios": ["build/**/*.ipa"],
        "windows": ["dist/*.exe"],
    }[target]


def artifact_snapshot(root: Path, patterns: list[str]) -> dict:
    previous = {}
    for pattern in patterns:
        for file in root.glob(pattern):
            if file.is_file() and not file.is_symlink():
                within(root, str(file.relative_to(root)))
                info = file.stat()
                previous[file] = (info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_ino)
                if len(previous) > 200:
                    raise ValueError("Narrow the artifact patterns to at most 200 candidate files")
    return previous


def file_digest(file: Path) -> str:
    digest = hashlib.sha256()
    with file.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cached_artifact_hashes(directory: Path, report: dict) -> set[str]:
    candidates = sorted(
        directory.glob("*.json"), key=lambda file: file.stat().st_mtime_ns, reverse=True
    )
    for file in candidates[:20]:
        if file.stem == report["id"]:
            continue
        try:
            previous = json.loads(file.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(previous, dict) or not previous.get("checks"):
            continue
        if (
            previous.get("state") == "complete"
            and previous.get("workspace") == report["workspace"]
            and previous.get("source_version") == report["source_version"]
            and previous.get("checks", [{}])[0].get("target") == report["checks"][0]["target"]
        ):
            return {
                item["sha256"]
                for item in previous.get("artifacts", [])
                if isinstance(item, dict) and isinstance(item.get("sha256"), str)
            }
    return set()


def with_live_output(report: dict, directory: Path) -> dict:
    if report.get("state") == "running" and report.get("checks"):
        file = directory / f"{report['id']}-step.log"
        if file.is_file():
            with file.open("rb") as stream:
                stream.seek(max(0, file.stat().st_size - 16000))
                report["checks"][0]["live_output"] = redact(
                    re.sub(
                        r"\x1b\[[0-9;]*[A-Za-z]", "", stream.read(16000).decode(errors="replace")
                    )
                )
    return report


def plan(
    root: Path, target: str, operation: str, provider: str = "vercel", site: str = ""
) -> dict:
    if target not in TARGETS or operation not in {"build", "deploy"} or provider not in PROVIDERS:
        raise ValueError("Choose a supported platform, operation and provider")
    if len(site) > 200 or (site and not re.fullmatch(r"[A-Za-z0-9_.-]+", site)):
        raise ValueError(
            "Site/project identifiers may contain letters, numbers, dots, dashes and underscores"
        )
    cfg = config(root)
    row = cfg.get("targets", {}).get(target, {})
    custom = row.get("build") or script(root, f"build:{target}")
    publish = row.get("deploy") or script(root, f"deploy:{target}")
    frontend = bool(
        web_build(root)
        or any(
            (within(root, value) / "index.html").is_file()
            for value in (
                [cfg["web_output"]]
                if cfg.get("web_output")
                else ["dist", "build", "out", "www", "."]
            )
        )
    )
    reason = ""
    if custom:
        executable = (
            os.access(root / custom[0], os.X_OK) and (root / custom[0]).is_file()
            if "/" in custom[0] and not Path(custom[0]).is_absolute()
            else bool(shutil.which(custom[0]))
        )
        if not executable and not (
            custom[0] in {"npm", "npx", "node", "pnpm", "yarn", "bun"}
            and release_tools.supported()
        ):
            reason = f"Install {custom[0]} on this job's computer to run its configured build."
    elif target == "web":
        remote_web = operation == "deploy" and provider in {"vercel", "railway", "project"}
        if not frontend and not (
            remote_web
            and any(
                (root / name).exists()
                for name in ("package.json", "Dockerfile", "requirements.txt", "pyproject.toml")
            )
        ):
            reason = (
                "No browser frontend detected. Add a web build or configure this "
                "project's build command."
            )
    elif target == "android" and (root / "android/gradlew").exists():
        if not release_tools.supported():
            reason = "Use a supported Android build computer or a configured cloud workflow."
    elif target == "ios":
        if platform.system() != "Darwin" or not shutil.which("xcodebuild"):
            reason = "iOS signing needs a Mac with Xcode, or a configured cloud build command."
        elif not (root / ".xwav/ExportOptions.plist").is_file():
            reason = "Configure .xwav/ExportOptions.plist with your Apple signing/export settings."
        elif not frontend:
            reason = "Configure a native iOS build command for this project."
    elif (
        target == "windows"
        and platform.system() != "Windows"
        and not shutil.which("wine")
        and not release_tools.wine_bootstrap_supported()
    ):
        reason = "Windows installers need Windows or Wine, or a configured cloud build command."
    elif not frontend:
        reason = (
            "No compatible browser frontend found. Configure this platform's native build command."
        )
    if (
        not custom
        and target != "web"
        and not reason
        and not shutil.which("npm")
        and not release_tools.supported()
    ):
        reason = "Install Node.js and npm on this job's computer for app conversion."
    if target == "android" and not custom and not reason:
        if not release_tools.supported() or (
            platform.system() == "Linux" and platform.machine() not in {"x86_64", "amd64"}
        ):
            reason = (
                "Automatic Android SDK setup requires Linux x64 or macOS; configure a cloud build."
            )
    if operation == "deploy" and not reason:
        if (
            target in {"android", "ios"}
            and not custom
            and not (root / "android/gradlew").exists()
            and not cfg.get("build_number")
        ):
            reason = "Set build_number in .xwav/release.json for a versioned store submission."
        elif target != "web" and not publish:
            reason = (
                "Connect a store publishing workflow using this project's deploy "
                "script or release configuration."
            )
        elif target == "web" and provider == "project" and not (publish or script(root, "deploy")):
            reason = "This project has no configured deployment command."
        elif target == "web" and provider == "cloudflare" and not site:
            reason = "Choose your existing Cloudflare Pages project name."
        elif (
            target == "web"
            and provider != "project"
            and not shutil.which("npx")
            and not release_tools.supported()
        ):
            reason = "Install Node.js/npm to use the selected deployment provider."
    return {
        "target": target,
        "operation": operation,
        "provider": provider,
        "site": site,
        "ready": not reason,
        "reason": reason,
        "setup": "Missing build tools are downloaded automatically and cached when you start.",
        "android_licenses_required": target == "android"
        and not custom
        and not (
            Path(
                os.environ.get("ANDROID_HOME")
                or os.environ.get("ANDROID_SDK_ROOT")
                or release_tools.cache_root() / "android-sdk"
            )
            / "licenses/android-sdk-license"
        ).is_file(),
        "steps": [
            {
                "id": "release",
                "name": f"{operation.title()} {target}",
                "platform": target,
                "category": "release",
                "status": "queued",
                "target": target,
                "operation": operation,
                "provider": provider,
                "site": site,
            }
        ],
    }


def safe_plan(root: Path, target: str, operation: str, provider: str, site: str) -> dict:
    try:
        return plan(root, target, operation, provider, site)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return {
            "target": target,
            "ready": False,
            "reason": redact(str(exc)),
            "android_licenses_required": False,
            "steps": [],
        }


def copy_web(root: Path, destination: Path) -> None:
    cfg = config(root)
    options = (
        [cfg["web_output"]] if cfg.get("web_output") else ["dist", "build", "out", "www", "."]
    )
    source = next(
        (
            within(root, value)
            for value in options
            if (within(root, value) / "index.html").is_file()
        ),
        None,
    )
    if source is None:
        raise ValueError(
            "No built index.html found. Configure web_output for a static export; "
            "server-only apps need a native/cloud build workflow."
        )
    destination.mkdir(parents=True, exist_ok=True)
    excluded = {
        ".git",
        ".xwav",
        "node_modules",
        ".venv",
        "venv",
        "android",
        "ios",
        "tests",
        "__pycache__",
    }
    allowed = {
        ".html",
        ".js",
        ".mjs",
        ".css",
        ".json",
        ".wasm",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".ico",
        ".webp",
        ".avif",
        ".woff",
        ".woff2",
        ".ttf",
        ".mp3",
        ".mp4",
        ".webm",
        ".txt",
        ".xml",
        ".webmanifest",
        ".map",
        ".pdf",
    }
    total = count = 0
    for parent, directories, files in os.walk(source, followlinks=False):
        directories[:] = [
            name
            for name in directories
            if name not in excluded
            and not name.startswith(".")
            and not (Path(parent) / name).is_symlink()
        ]
        for name in files:
            path = Path(parent) / name
            if (
                path.is_symlink()
                or name.startswith(".")
                or path.suffix.lower() not in allowed
                or name in {"package.json", "package-lock.json", "server.js", "server.mjs"}
            ):
                continue
            count += 1
            total += path.stat().st_size
            if count > 20000 or total > 256 * 1024 * 1024:
                raise ValueError("Browser assets exceed 20,000 files or 256 MiB")
            output = destination / path.relative_to(source)
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, output)


def stage_source(root: Path, destination: Path) -> None:
    """Upload source without job caches, signing material or local credentials."""
    destination.mkdir(parents=True, exist_ok=True)
    excluded = {"node_modules", "venv", "__pycache__", "dist", "build", "out", "coverage"}
    dotfiles = {
        ".gitignore",
        ".vercelignore",
        ".railwayignore",
        ".dockerignore",
        ".nvmrc",
        ".node-version",
    }
    count = total = 0
    for parent, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [
            name
            for name in dirs
            if name not in excluded
            and not name.startswith(".")
            and not (Path(parent) / name).is_symlink()
        ]
        for name in files:
            file = Path(parent) / name
            if (
                file.is_symlink()
                or (name.startswith(".") and name not in dotfiles)
                or file.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"}
                or name == "credentials.json"
                or name.startswith("service-account")
            ):
                continue
            count += 1
            total += file.stat().st_size
            if count > 20000 or total > 256 * 1024 * 1024:
                raise ValueError("Deployment source exceeds 20,000 files or 256 MiB")
            output = destination / file.relative_to(root)
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, output)
    link = root / ".vercel/project.json"
    if link.is_file() and not link.is_symlink():
        within(root, ".vercel/project.json")
        (destination / ".vercel").mkdir(exist_ok=True)
        shutil.copyfile(link, destination / ".vercel/project.json")


def redact(text: str) -> str:
    for key, value in os.environ.items():
        if len(value) >= 6 and any(
            word in key.lower()
            for word in ("token", "secret", "password", "api_key", "_b64", "_json")
        ):
            text = text.replace(value, "[redacted]")
    return text


def artifact_valid(path: Path, target: str) -> bool:
    if target == "windows":
        with path.open("rb") as file:
            header = file.read(64)
            if path.suffix.lower() != ".exe" or len(header) < 64 or header[:2] != b"MZ":
                return False
            file.seek(int.from_bytes(header[60:64], "little"))
            return file.read(4) == b"PE\0\0"
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if target == "android":
                return path.suffix.lower() in {".apk", ".aab"} and (
                    (
                        "AndroidManifest.xml" in names
                        and any(re.fullmatch(r"classes[0-9]*\.dex", name) for name in names)
                    )
                    or "base/manifest/AndroidManifest.xml" in names
                )
            if target == "ios":
                return (
                    path.suffix.lower() == ".ipa"
                    and any(re.fullmatch(r"Payload/[^/]+\.app/Info.plist", name) for name in names)
                    and any(".app/_CodeSignature/CodeResources" in name for name in names)
                )
            return "index.html" in names
    except (OSError, zipfile.BadZipFile):
        return False


def _worker(directory: Path, run_id: str, save, execute, fingerprint) -> None:
    report_file = directory / f"{run_id}.json"
    report = json.loads(report_file.read_text())
    root = Path(report["workspace"])
    check = report["checks"][0]
    target, operation, provider, site = (
        check[key] for key in ("target", "operation", "provider", "site")
    )
    cancel = directory / f"{run_id}.cancel"
    output = root / ".xwav/releases/artifacts" / run_id
    work = root / ".xwav/releases/work" / run_id
    upload = work / f"xwav-{directory.name[:12]}"
    cfg = config(root)
    row = cfg.get("targets", {}).get(target, {})
    output.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    report["artifacts"] = []
    report["worker_pid"] = os.getpid()
    check.update(status="running", output="", phase="Preparing")
    save(report_file, report)
    started = time.monotonic()

    def run(command: list[str], cwd: Path, phase: str) -> None:
        check["phase"] = phase
        save(report_file, report)
        if cancel.exists():
            raise RuntimeError("Cancelled")
        result = execute(
            command,
            cwd,
            max(1, int(1800 - (time.monotonic() - started))),
            cancel,
            directory / f"{run_id}-step.log",
        )
        check["output"] = (
            check["output"] + "\n" + redact(result.get("output", result.get("reason", "")))
        )[-16000:]
        save(report_file, report)
        if result["status"] != "passed":
            raise RuntimeError(
                result.get("reason")
                or f"{phase} failed (exit {result.get('exit_code')}). See build log."
            )

    def progress(phase: str) -> None:
        check["phase"] = phase
        save(report_file, report)

    try:
        current = plan(root, target, operation, provider, site)
        if not current["ready"]:
            raise ValueError(current["reason"])
        custom = row.get("build") or script(root, f"build:{target}")
        cached_hashes = cached_artifact_hashes(directory, report)
        previous_artifacts = artifact_snapshot(
            root, row.get("artifacts") or default_patterns(target)
        )
        remote_web = (
            target == "web"
            and operation == "deploy"
            and provider in {"vercel", "railway", "project"}
        )
        needs_project_build = not remote_web or bool(custom)
        needs_node = bool(
            custom and custom[0] in {"npm", "npx", "node", "pnpm", "yarn", "bun"}
        ) or bool(
            not custom
            and (
                target != "web"
                or web_build(root)
                or (operation == "deploy" and provider != "project")
            )
        )
        release_tools.prepare(
            target if not custom else "web",
            needs_node=needs_node,
            accept_android_licenses=check.get("accept_android_licenses", False),
            cancel=cancel,
            deadline=started + 1800,
            run=run,
            progress=progress,
            package_manager=package_manager(root) if needs_node and needs_project_build else None,
        )
        patterns = row.get("artifacts", [])
        pkg = package(root)
        if (
            needs_project_build
            and (pkg.get("dependencies") or pkg.get("devDependencies"))
            and not (root / "node_modules").is_dir()
        ):
            if web_build(root) or script(root, f"build:{target}"):
                manager = package_manager(root).split("@")[0]
                if manager == "npm":
                    install = [
                        "npm",
                        "ci" if (root / "package-lock.json").exists() else "install",
                        "--no-audit",
                        "--no-fund",
                    ]
                    if not (root / "package-lock.json").exists():
                        install += ["--package-lock=false"]
                else:
                    locks = {
                        "pnpm": ["pnpm-lock.yaml"],
                        "yarn": ["yarn.lock"],
                        "bun": ["bun.lock", "bun.lockb"],
                    }[manager]
                    locked = any((root / lock).exists() for lock in locks)
                    flags = (
                        ["--frozen-lockfile"]
                        if locked
                        else (
                            ["--lockfile=false", "--no-frozen-lockfile"]
                            if manager == "pnpm"
                            else ["--no-lockfile"]
                            if manager == "yarn"
                            else ["--no-save"]
                        )
                    )
                    install = [manager, "install", *flags]
                run(install, root, "Installing cached project dependencies")
        if custom:
            run(custom, root, "Building project")
        elif remote_web:
            # These providers build the source with their deployment environment.
            pass
        elif target == "android" and (root / "android/gradlew").exists():
            if any(root.glob("capacitor.config.*")):
                browser_build = web_build(root)
                if browser_build:
                    run(browser_build, root, "Updating browser frontend")
                run(
                    ["npx", "--no-install", "cap", "sync", "android"],
                    root,
                    "Syncing Android assets and plugins",
                )
            run(
                ["sh", "gradlew", "bundleRelease" if operation == "deploy" else "assembleDebug"],
                root / "android",
                "Building Android",
            )
        else:
            build = web_build(root)
            if build:
                run(build, root, "Building browser frontend")
            copy_web(root, work / "web")
            if target != "web":
                adapter = root / ".xwav/releases/adapters" / directory.name / target
                adapter.mkdir(parents=True, exist_ok=True)
                app_name = str(cfg.get("app_name") or package(root).get("name") or root.name)
                slug = re.sub(r"[^a-z0-9]", "", app_name.lower())[:40] or "app"
                app_id = str(cfg.get("app_id") or f"app.xwav.app{slug}")
                shutil.rmtree(adapter / "www", ignore_errors=True)
                shutil.copytree(work / "web", adapter / "www")
                manifest: dict[str, Any] = {
                    "name": f"xwav-{slug}",
                    "version": str(cfg.get("app_version") or pkg.get("version") or "1.0.0"),
                    "private": True,
                }
                if target == "windows":
                    manifest.update(
                        main="main.cjs",
                        devDependencies={"electron": "^43.0.0", "electron-builder": "^26.0.0"},
                        build={
                            "appId": app_id,
                            "productName": app_name,
                            "files": ["main.cjs", "www/**/*"],
                            "directories": {"output": "dist"},
                            "win": {"target": "nsis"},
                        },
                    )
                    (adapter / "main.cjs").write_text(
                        "const {app,BrowserWindow,protocol,net}=require('electron');\n"
                        "const path=require('node:path');\n"
                        "const fs=require('node:fs');\n"
                        "const {pathToFileURL}=require('node:url');\n"
                        "protocol.registerSchemesAsPrivileged([{scheme:'xwav',privileges:{"
                        "standard:true,secure:true,supportFetchAPI:true,corsEnabled:true}}]);\n"
                        "app.whenReady().then(()=>{\n"
                        "const root=path.join(__dirname,'www');\n"
                        "protocol.handle('xwav',request=>{\n"
                        "let file=path.resolve(root,'.'+decodeURIComponent(new "
                        "URL(request.url).pathname));\n"
                        "if(file!==root&&!file.startsWith(root+path.sep))"
                        "return new Response('Forbidden',{status:403});\n"
                        "if(!fs.existsSync(file)||!fs.statSync(file).isFile())"
                        "file=path.join(root,'index.html');\n"
                        "return net.fetch(pathToFileURL(file).toString());});\n"
                        "const w=new BrowserWindow({width:1200,height:800,webPreferences:{"
                        "nodeIntegration:false,contextIsolation:true,sandbox:true}});\n"
                        "w.webContents.setWindowOpenHandler(()=>({action:'deny'}));\n"
                        "w.loadURL('xwav://app/index.html');});\n"
                        "app.on('window-all-closed',()=>app.quit());\n"
                    )
                else:
                    dependencies = pkg.get("dependencies", {})
                    core_version = dependencies.get("@capacitor/core", "^8.0.0")
                    plugins = {
                        name: version
                        for name, version in dependencies.items()
                        if (name.startswith(("@capacitor", "capacitor-")))
                        and name
                        not in {
                            "@capacitor/core",
                            "@capacitor/cli",
                            "@capacitor/android",
                            "@capacitor/ios",
                        }
                    }
                    manifest.update(
                        dependencies={
                            **plugins,
                            "@capacitor/core": core_version,
                            f"@capacitor/{target}": core_version,
                        },
                        devDependencies={"@capacitor/cli": core_version},
                    )
                    mobile_config = {"appId": app_id, "appName": app_name, "webDir": "www"}
                    settings = adapter / "capacitor.config.json"
                    if settings.exists() and json.loads(settings.read_text()) != mobile_config:
                        shutil.rmtree(adapter / target, ignore_errors=True)
                    settings.write_text(json.dumps(mobile_config))
                serialized = json.dumps(manifest, sort_keys=True)
                manifest_file = adapter / "package.json"
                install = (
                    not manifest_file.exists()
                    or manifest_file.read_text() != serialized
                    or not (adapter / "node_modules").is_dir()
                )
                manifest_file.write_text(serialized)
                if install:
                    run(
                        ["npm", "install", "--no-audit", "--no-fund"],
                        adapter,
                        "Preparing cached packaging tools",
                    )
                if target == "windows":
                    run(
                        [
                            "npx",
                            "--no-install",
                            "electron-builder",
                            "--win",
                            "nsis",
                            "--publish",
                            "never",
                            f"-c.directories.output={output}",
                        ],
                        adapter,
                        "Packaging Windows installer",
                    )
                    patterns = [str(output.relative_to(root) / "*.exe")]
                else:
                    if not (adapter / target).exists():
                        run(
                            ["npx", "--no-install", "cap", "add", target],
                            adapter,
                            f"Creating {target} app",
                        )
                    run(
                        ["npx", "--no-install", "cap", "sync", target],
                        adapter,
                        "Syncing browser assets",
                    )
                    if target == "android":
                        gradle = adapter / "android/app/build.gradle"
                        text = gradle.read_text()
                        text, code_count = re.subn(
                            r"versionCode\s+\d+", f"versionCode {cfg.get('build_number', 1)}", text
                        )
                        text, name_count = re.subn(
                            r'versionName\s+"[^"\n]*"',
                            lambda _match: "versionName " + json.dumps(manifest["version"]),
                            text,
                        )
                        if code_count != 1 or name_count != 1:
                            raise ValueError(
                                "Configure a native build command for this Android Gradle template"
                            )
                        gradle.write_text(text)
                        run(
                            [
                                "sh",
                                "gradlew",
                                "bundleRelease" if operation == "deploy" else "assembleDebug",
                            ],
                            adapter / "android",
                            "Building Android package",
                        )
                        patterns = [
                            str(adapter.relative_to(root) / "android/app/build/outputs/**/*.apk"),
                            str(adapter.relative_to(root) / "android/app/build/outputs/**/*.aab"),
                        ]
                    else:
                        archive = work / "App.xcarchive"
                        export = plistlib.loads((root / ".xwav/ExportOptions.plist").read_bytes())
                        team = (
                            [f"DEVELOPMENT_TEAM={export['teamID']}"]
                            if export.get("teamID")
                            else []
                        )
                        run(
                            [
                                "xcodebuild",
                                "-project",
                                "ios/App/App.xcodeproj",
                                "-scheme",
                                "App",
                                "-configuration",
                                "Release",
                                "-archivePath",
                                str(archive),
                                "archive",
                                "-allowProvisioningUpdates",
                                *(
                                    [
                                        "CODE_SIGN_STYLE=Manual",
                                        "CODE_SIGN_IDENTITY=Apple Distribution",
                                        "PROVISIONING_PROFILE_SPECIFIER="
                                        + os.environ["XWAV_IOS_PROFILE_NAME"],
                                    ]
                                    if os.environ.get("XWAV_IOS_PROFILE_NAME")
                                    else []
                                ),
                                "MARKETING_VERSION="
                                + manifest["version"].split("-")[0].split("+")[0],
                                "CURRENT_PROJECT_VERSION=" + str(cfg.get("build_number", 1)),
                                *team,
                            ],
                            adapter,
                            "Archiving signed iOS app",
                        )
                        run(
                            [
                                "xcodebuild",
                                "-exportArchive",
                                "-archivePath",
                                str(archive),
                                "-exportPath",
                                str(output),
                                "-exportOptionsPlist",
                                str(root / ".xwav/ExportOptions.plist"),
                            ],
                            adapter,
                            "Exporting signed iOS installer",
                        )
                        patterns = [str(output.relative_to(root) / "*.ipa")]
        if target == "web" and not remote_web:
            if not (work / "web/index.html").is_file():
                copy_web(root, work / "web")
            shutil.make_archive(str(output / "web"), "zip", work / "web")
            patterns = [str(output.relative_to(root) / "web.zip")]
        elif target != "web" and not patterns:
            patterns = default_patterns(target)
        seen = set()
        total_bytes = 0
        for pattern in patterns:
            for file in root.glob(pattern):
                resolved = within(root, str(file.relative_to(root)))
                if file.is_symlink() or not file.is_file() or resolved in seen:
                    continue
                seen.add(resolved)
                info = file.stat()
                if (
                    previous_artifacts.get(file)
                    == (
                        info.st_size,
                        info.st_mtime_ns,
                        info.st_ctime_ns,
                        info.st_ino,
                    )
                    and file_digest(file) not in cached_hashes
                ):
                    continue
                size = info.st_size
                if size > 512 * 1024 * 1024:
                    raise ValueError("Release artifact exceeds 512 MiB")
                if not artifact_valid(file, target):
                    continue
                total_bytes += size
                if len(seen) > 20 or total_bytes > 512 * 1024 * 1024:
                    raise ValueError("Release artifacts exceed 20 files or 512 MiB")
                destination = output / file.name
                if destination.resolve() != resolved:
                    if destination.exists():
                        raise ValueError("Artifact names must be unique")
                    shutil.copyfile(file, destination)
                checksum = file_digest(destination)
                report["artifacts"].append(
                    {
                        "name": file.name,
                        "path": str(destination.relative_to(root)),
                        "bytes": size,
                        "sha256": checksum,
                        "installable": target != "web" and file.suffix != ".aab",
                    }
                )
        if not report["artifacts"] and not remote_web:
            raise ValueError(
                "Build did not produce a new or updated valid package. Configure this target's "
                "artifact paths; iOS requires a signed IPA."
            )
        if cancel.exists():
            raise RuntimeError("Cancelled")
        if fingerprint(root) != report["source_version"]:
            raise ValueError(
                "Project source changed during the build. Run again before deployment."
            )
        if operation == "deploy":
            publish = row.get("deploy") or script(root, f"deploy:{target}")
            if target == "web":
                if provider == "project":
                    publish = publish or script(root, "deploy")
                elif provider == "vercel":
                    stage_source(root, upload)
                    cached_link = directory / "vercel-project.json"
                    link = upload / ".vercel/project.json"
                    if cached_link.is_file() and not link.exists():
                        link.parent.mkdir(exist_ok=True)
                        shutil.copyfile(cached_link, link)
                    publish = [
                        "npx",
                        "--yes",
                        "vercel",
                        "deploy",
                        str(upload),
                        "--prod",
                        "--yes",
                    ]
                    if os.environ.get("VERCEL_TOKEN"):
                        publish += ["--token", os.environ["VERCEL_TOKEN"]]
                elif provider == "netlify":
                    publish = [
                        "npx",
                        "--yes",
                        "netlify-cli",
                        "deploy",
                        "--prod",
                        "--dir",
                        str(work / "web"),
                        "--json",
                        "--no-build",
                    ]
                    if site:
                        publish += ["--site", site]
                elif provider == "cloudflare":
                    publish = [
                        "npx",
                        "--yes",
                        "wrangler",
                        "pages",
                        "deploy",
                        str(work / "web"),
                        "--project-name",
                        site,
                    ]
                elif provider == "railway":
                    stage_source(root, upload)
                    publish = [
                        "npx",
                        "--yes",
                        "@railway/cli",
                        "up",
                        str(upload),
                        "--path-as-root",
                        "--ci",
                    ]
                    if site:
                        publish += ["--service", site]
            if not publish:
                raise ValueError("No deployment workflow configured")
            if target == "web" and os.environ.get("XWAV_RELEASE_CHANNEL") == "testing":
                if provider in {"vercel", "netlify"}:
                    publish = [arg for arg in publish if arg != "--prod"]
                elif provider == "cloudflare":
                    publish += ["--branch", "xwav-preview"]
                elif provider in {"railway", "project"}:
                    # These providers use separately connected staging environments.
                    if os.environ.get("XWAV_STAGING_CONFIRMED") != "true":
                        raise ValueError(
                            "Configure an isolated staging destination and set "
                            "XWAV_STAGING_CONFIRMED=true in its GitHub environment"
                        )
            if fingerprint(root) != report["source_version"]:
                raise ValueError("Project source changed before upload. Build again.")
            run(publish, root, "Publishing to destination")
            if provider == "vercel" and target == "web":
                link = upload / ".vercel/project.json"
                if link.is_file() and not link.is_symlink():
                    shutil.copyfile(link, directory / "vercel-project.json")
            urls = re.findall(r"https://[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_./?=-]*)?", check["output"])
            report["urls"] = list(
                dict.fromkeys(
                    url
                    for url in urls
                    if url.split("/")[2]
                    .lower()
                    .endswith((".vercel.app", ".netlify.app", ".pages.dev", ".railway.app"))
                )
            )[-5:]
        check.update(
            status="passed",
            phase="Submitted"
            if operation == "deploy" and target != "web"
            else "Deployed"
            if operation == "deploy"
            else "Build ready",
        )
        report["state"] = "complete"
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, zipfile.BadZipFile) as exc:
        check.update(status="cancelled" if cancel.exists() else "failed", reason=redact(str(exc)))
        report.update(state="cancelled" if cancel.exists() else "error", error=redact(str(exc)))
        # Failed or interrupted runs never expose partly written installers.
        report["artifacts"] = []
    try:
        changed = fingerprint(root) != report["source_version"]
    except (OSError, ValueError, TypeError, KeyError):
        changed = True
    report.update(finished_at=time.time(), source_changed=changed)
    check["duration"] = round(time.monotonic() - started, 2)
    save(report_file, report)
    shutil.rmtree(work, ignore_errors=True)
    if report["state"] != "complete":
        shutil.rmtree(output, ignore_errors=True)
    else:
        keep = {item["name"] for item in report["artifacts"]}
        for generated in output.iterdir():
            if generated.name not in keep:
                if generated.is_dir() and not generated.is_symlink():
                    shutil.rmtree(generated, ignore_errors=True)
                else:
                    generated.unlink(missing_ok=True)


def worker(directory: Path, run_id: str, save, execute, fingerprint) -> None:
    """Persist setup/finalization failures as well as command failures."""
    try:
        _worker(directory, run_id, save, execute, fingerprint)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        file = directory / f"{run_id}.json"
        report = json.loads(file.read_text())
        cancelled = (directory / f"{run_id}.cancel").exists()
        report.update(
            state="cancelled" if cancelled else "error",
            error=redact(str(exc)),
            artifacts=[],
            finished_at=time.time(),
        )
        if report.get("checks"):
            report["checks"][0].update(
                status="cancelled" if cancelled else "failed", reason=redact(str(exc))
            )
        save(file, report)
        root = Path(report["workspace"])
        for folder in ("work", "artifacts"):
            shutil.rmtree(root / ".xwav/releases" / folder / run_id, ignore_errors=True)

"""Persistent, bounded pre-production checks transported to an owner's job runtime."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import runpy
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import suppress
from pathlib import Path

CATEGORIES = (
    "unit",
    "integration",
    "functional",
    "regression",
    "e2e",
    "security",
    "static",
    "usability",
    "accessibility",
    "smoke",
)
PLATFORMS = ("shared", "web", "android", "ios")
QUALITY_ROOT = Path("/opt/xwav-quality")
IGNORED = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".next",
    "dist",
    "build",
    "coverage",
    "test-results",
    ".xwav",
}


def save(path: Path, data: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data))
    temporary.replace(path)


def fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    count = 0
    for directory, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED and not d.startswith("."))
        for name in sorted(files):
            path = Path(directory) / name
            if path.is_symlink():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            digest.update(f"{path.relative_to(root)}:{stat.st_size}:{stat.st_mtime_ns}".encode())
            count += 1
            if count >= 5000:
                return digest.hexdigest()
    return digest.hexdigest()


def discover(root: Path) -> list[dict]:
    checks: list[dict] = []

    def add(
        category: str,
        name: str,
        command: list[str] | None = None,
        platform: str = "shared",
        **extra,
    ) -> None:
        checks.append(
            {
                "id": str(len(checks)),
                "category": category,
                "name": name,
                "platform": platform,
                "command": command,
                "status": "pending" if command or extra.get("builtin") else "blocked",
                "reason": "No test suite configured for this category."
                if not command and not extra.get("builtin")
                else "",
                "cwd": ".",
                "timeout": 180,
                **extra,
            }
        )

    config = root / ".xwav" / "preproduction.json"
    if config.exists():
        configured = json.loads(config.read_text())
        rows = configured.get("checks") if isinstance(configured, dict) else None
        if not isinstance(rows, list) or len(rows) > 40:
            raise ValueError(".xwav/preproduction.json needs a checks array (maximum 40).")
        for row in rows:
            if (
                not isinstance(row, dict)
                or row.get("category") not in CATEGORIES
                or row.get("platform", "shared") not in PLATFORMS
            ):
                raise ValueError("Each check needs a supported category and platform.")
            command = row.get("command")
            if (
                not isinstance(command, list)
                or not command
                or not all(isinstance(arg, str) and arg and len(arg) < 4096 for arg in command)
            ):
                raise ValueError("Commands must be nonempty argument arrays.")
            cwd = (root / row.get("cwd", ".")).resolve()
            if not cwd.is_relative_to(root) or not cwd.is_dir():
                raise ValueError("Check cwd must stay inside this workspace.")
            timeout = row.get("timeout", 180)
            if type(timeout) is not int or not 1 <= timeout <= 600:
                raise ValueError("Check timeout must be between 1 and 600 seconds.")
            add(
                row["category"],
                str(row.get("name", row["category"]))[:160],
                command,
                row.get("platform", "shared"),
                cwd=str(cwd.relative_to(root)),
                timeout=timeout,
            )
    else:
        packages = [
            path
            for pattern in (
                "package.json",
                "*/package.json",
                "apps/*/package.json",
                "packages/*/package.json",
            )
            for path in root.glob(pattern)
            if not any(part in IGNORED for part in path.relative_to(root).parts)
            and not path.is_symlink()
            and path.resolve().is_relative_to(root)
        ][:20]
        for package in sorted(set(packages)):
            scripts = json.loads(package.read_text()).get("scripts", {})
            manager = (
                "pnpm"
                if (root / "pnpm-lock.yaml").exists()
                else "yarn"
                if (root / "yarn.lock").exists()
                else "npm"
            )
            for category, names in {
                "unit": ("test:unit", "test"),
                "integration": ("test:integration",),
                "functional": ("test:functional",),
                "regression": ("test:regression",),
                "e2e": ("test:e2e", "e2e"),
                "security": ("test:security", "security"),
                "static": ("lint", "typecheck", "type-check"),
                "accessibility": ("test:a11y", "test:accessibility"),
                "usability": ("test:usability",),
                "smoke": ("test:smoke",),
            }.items():
                for name in names:
                    if name in scripts:
                        add(
                            category,
                            f"Project script: {name}",
                            [manager, "run", name],
                            env={"CI": "true"},
                            cwd=str(package.parent.relative_to(root)),
                        )
                        if category != "static":
                            break
        if (root / "pyproject.toml").exists() or (root / "pytest.ini").exists():
            for category, directory in {
                "unit": "tests/unit",
                "integration": "tests/integration",
                "functional": "tests/functional",
                "regression": "tests/regression",
                "e2e": "tests/e2e",
                "smoke": "tests/smoke",
            }.items():
                if (root / directory).is_dir():
                    add(
                        category,
                        f"Pytest {directory}",
                        [sys.executable, "-m", "pytest", directory, "-q"],
                    )
            if not any(c["category"] == "unit" for c in checks) and (root / "tests").is_dir():
                add(
                    "unit",
                    "Existing Python test suite (classification unverified)",
                    [sys.executable, "-m", "pytest", "tests", "-q"],
                )
            if shutil.which("ruff"):
                add("static", "Ruff static analysis", ["ruff", "check", "."])
        if (root / "pubspec.yaml").exists() and (root / "test").is_dir():
            add("unit", "Flutter test suite", ["flutter", "test"])
        android = root / "android"
        if (android / "gradlew").is_file():
            add(
                "unit",
                "Android unit tests",
                ["sh", "gradlew", "testDebugUnitTest"],
                "android",
                cwd="android",
            )
            add("static", "Android lint", ["sh", "gradlew", "lintDebug"], "android", cwd="android")
        if (root / "package-lock.json").is_file() and shutil.which("npm"):
            add(
                "security",
                "Dependency vulnerability audit",
                ["npm", "audit", "--audit-level=moderate"],
            )
        if not any(c["category"] == "static" for c in checks):
            javascript = sorted(
                str(path.relative_to(root))
                for path in root.glob("*.js")
                if not path.is_symlink() and path.is_file()
            )[:100]
            if javascript and shutil.which("node"):
                for source in javascript:
                    add(
                        "static",
                        f"JavaScript syntax: {source} (baseline only)",
                        ["node", "--check", source],
                    )
        add("security", "Source secret scan (baseline only)", builtin="secrets")
        for platform in ("web", "android", "ios"):
            qualifier = "responsive browser" if platform != "web" else "browser"
            for category in ("smoke", "functional", "usability", "accessibility"):
                add(
                    category,
                    f"{'iOS' if platform == 'ios' else platform.title()} {qualifier} baseline",
                    platform=platform,
                    builtin="browser",
                )
    for category in CATEGORIES:
        if not any(c["category"] == category for c in checks):
            add(category, f"{category.title()} suite")
    for platform, present in (
        ("android", (root / "android").exists()),
        ("ios", (root / "ios").exists()),
    ):
        if not any(c["platform"] == platform and c.get("command") for c in checks):
            add(
                "e2e",
                f"Native {'iOS' if platform == 'ios' else 'Android'} device tests",
                platform=platform,
                status="blocked" if present else "not_applicable",
                reason=(
                    "Configure a simulator/device test command; responsive "
                    "previews are not native tests."
                )
                if present
                else "No native project detected. Responsive layouts are checked separately.",
            )
    return checks


def terminate(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=2)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        pass
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)


def execute(
    command: list[str], cwd: Path, timeout: int, cancel: Path, log: Path, env: dict | None = None
) -> dict:
    started = time.monotonic()
    with log.open("wb") as output:
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=output,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                env={**os.environ, "CI": "true", **(env or {})},
                start_new_session=True,
            )
        except OSError as exc:
            return {"status": "blocked", "reason": str(exc), "duration": 0}
        reason = ""
        while process.poll() is None:
            if (
                cancel.exists()
                or time.monotonic() - started > timeout
                or log.stat().st_size > 2_000_000
            ):
                reason = (
                    "Cancelled"
                    if cancel.exists()
                    else "Timeout"
                    if time.monotonic() - started > timeout
                    else "Output limit exceeded"
                )
                terminate(process)
                break
            time.sleep(0.1)
    text = log.read_bytes()[-16000:].decode("utf-8", errors="replace")
    return {
        "status": "cancelled"
        if reason == "Cancelled"
        else "failed"
        if reason or process.returncode
        else "passed",
        "reason": reason,
        "exit_code": process.returncode,
        "output": re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text),
        "output_truncated": log.stat().st_size > 16000,
        "duration": round(time.monotonic() - started, 2),
    }


def browser_audit(root: Path, platform: str, preview_file: Path) -> dict:
    discover_preview = runpy.run_path(str(preview_file))["preview"]
    status = discover_preview()
    for _ in range(15):
        if status.get("state") != "starting":
            break
        time.sleep(1)
        status = discover_preview()
    if status.get("state") != "ready":
        raise RuntimeError(str(status.get("message", "No runnable web app")))
    port = int(status["port"])
    if not 1 <= port <= 65535:
        raise ValueError("Invalid local preview port")
    if (QUALITY_ROOT / "browsers").is_dir():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(QUALITY_ROOT / "browsers"))
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        from urllib.request import urlopen

        with urlopen(f"http://127.0.0.1:{port}/", timeout=10) as response:
            ready = response.status == 200 and "html" in response.headers.get("Content-Type", "")
        results = {
            category: {
                "status": "blocked",
                "reason": (
                    "Browser tooling unavailable. Use the current Xwav host image "
                    "or configure a browser test suite."
                ),
            }
            for category in ("functional", "usability", "accessibility")
        }
        results["smoke"] = {
            "status": "passed" if ready else "failed",
            "output": "Local HTTP/HTML smoke only. Browser tooling unavailable.",
        }
        return results
    width, height = {"web": (1440, 900), "android": (412, 915), "ios": (393, 852)}[platform]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": width, "height": height},
                is_mobile=platform != "web",
                has_touch=platform != "web",
            )
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(
                f"http://127.0.0.1:{port}/", wait_until="domcontentloaded", timeout=20000
            )
            page.wait_for_timeout(500)
            metrics = page.evaluate(
                """() => ({title: document.title, body: !!document.body?.children.length,
                  overflow: document.documentElement.scrollWidth > innerWidth + 1,
                  viewport: !!document.querySelector('meta[name=viewport]')})"""
            )
            result = {
                "smoke": {
                    "status": "passed"
                    if response and response.ok and metrics["body"]
                    else "failed",
                    "output": f"HTTP {response.status if response else 'none'}; "
                    f"title={metrics['title']}",
                },
                "functional": {
                    "status": "failed" if errors else "passed",
                    "output": (
                        "Browser load/runtime errors only; configure application "
                        "workflows for functional coverage.\\n"
                    )
                    + "\n".join(errors),
                },
                "usability": {
                    "status": "failed"
                    if metrics["overflow"] or (platform != "web" and not metrics["viewport"])
                    else "passed",
                    "output": f"Horizontal overflow={metrics['overflow']}; "
                    f"viewport meta={metrics['viewport']}. "
                    "Baseline only; human usability review remains necessary.",
                },
            }
            axe = next(
                (
                    path
                    for path in (
                        root / "node_modules/axe-core/axe.min.js",
                        QUALITY_ROOT / "node_modules/axe-core/axe.min.js",
                    )
                    if path.is_file()
                ),
                None,
            )
            if axe:
                page.add_script_tag(path=str(axe))
                findings = page.evaluate(
                    """async () => { const result = await axe.run();
                    return {violations: result.violations.map(v => ({id:v.id,
                      impact:v.impact, description:v.description, nodes:v.nodes.length})),
                      incomplete:result.incomplete.length}; }"""
                )
                result["accessibility"] = {
                    "status": "failed" if findings["violations"] else "passed",
                    "output": json.dumps(findings)
                    + (
                        "\\nAutomated axe scan only; keyboard/screen-reader review "
                        "remains necessary."
                    ),
                }
            else:
                result["accessibility"] = {
                    "status": "blocked",
                    "reason": (
                        "axe-core is not installed. Configure an accessibility "
                        "suite or install it in the project."
                    ),
                }
            return result
        finally:
            browser.close()


def secret_scan(root: Path) -> dict:
    findings = []
    count = 0
    for directory, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in IGNORED and not (Path(directory) / d).is_symlink()]
        for name in files:
            path = Path(directory) / name
            if path.is_symlink() or path.stat().st_size > 300000:
                continue
            count += 1
            if count > 5000:
                return {
                    "status": "blocked",
                    "reason": "Scan exceeds 5000 files; configure a security suite.",
                }
            text = path.read_bytes()
            if b"\0" in text:
                continue
            if re.search(
                rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}", text
            ):
                findings.append(str(path.relative_to(root)))
    return {
        "status": "failed" if findings else "passed",
        "output": (
            "Baseline high-confidence secret patterns only; not a "
            "dependency, SAST, DAST or penetration audit.\\n"
        )
        + "\n".join(findings),
    }


def worker(directory: Path, run_id: str) -> None:
    report_file = directory / f"{run_id}.json"
    report = json.loads(report_file.read_text())
    report["worker_pid"] = os.getpid()
    save(report_file, report)
    root = Path(report["workspace"])
    cancel = directory / f"{run_id}.cancel"
    started = time.monotonic()
    reused: dict[str, dict] = {}
    browser_results: dict[str, dict] = {}
    try:
        for check in report["checks"]:
            if check["status"] != "pending":
                continue
            if cancel.exists() or time.monotonic() - started > 1800:
                check.update(
                    status="cancelled" if cancel.exists() else "blocked",
                    reason="Cancelled" if cancel.exists() else "Overall 30-minute limit reached",
                )
                continue
            check.update(status="running", started_at=time.time())
            save(report_file, report)
            begin = time.monotonic()
            try:
                if check.get("builtin") == "secrets":
                    result = secret_scan(root)
                elif check.get("builtin") == "browser":
                    platform = check["platform"]
                    if platform not in browser_results:
                        audit_file = directory / f"{run_id}-{platform}.audit.json"
                        execution = execute(
                            [
                                sys.executable,
                                str(directory / "runtime.py"),
                                "--audit",
                                str(root),
                                platform,
                                str(directory / "preview.py"),
                                str(audit_file),
                            ],
                            root,
                            min(70, max(1, int(1800 - (time.monotonic() - started)))),
                            cancel,
                            directory / f"{run_id}-{platform}.log",
                        )
                        browser_results[platform] = (
                            json.loads(audit_file.read_text())
                            if execution["status"] == "passed" and audit_file.exists()
                            else {
                                category: {
                                    "status": "cancelled" if cancel.exists() else "blocked",
                                    "reason": "Browser baseline unavailable: "
                                    + str(
                                        execution.get("output") or execution.get("reason") or ""
                                    )[-2000:],
                                }
                                for category in (
                                    "smoke",
                                    "functional",
                                    "usability",
                                    "accessibility",
                                )
                            }
                        )
                    result = browser_results[platform][check["category"]]
                else:
                    key = json.dumps(
                        [check["command"], check["cwd"], check.get("env"), check["timeout"]]
                    )
                    if key in reused:
                        result = {**reused[key], "reused": True}
                    else:
                        result = execute(
                            check["command"],
                            root / check["cwd"],
                            min(
                                check["timeout"], max(1, int(1800 - (time.monotonic() - started)))
                            ),
                            cancel,
                            directory / f"{run_id}-{check['id']}.log",
                            check.get("env"),
                        )
                        reused[key] = result
                check.update(result)
            except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
                check.update(status="error", reason=f"{type(exc).__name__}: {exc}")
            check.setdefault("duration", round(time.monotonic() - begin, 2))
            save(report_file, report)
        report.update(
            state="cancelled" if cancel.exists() else "complete",
            finished_at=time.time(),
            source_changed=fingerprint(root) != report["source_version"],
        )
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        report.update(state="error", error=str(exc), finished_at=time.time())
    save(report_file, report)


def report_directory(root: Path, session_id: str, kind: str) -> Path:
    key = hashlib.sha256(f"{session_id}:{root}".encode()).hexdigest()
    return (
        Path(os.environ.get("XWAV_TEST_REPORT_ROOT") or tempfile.gettempdir())
        / f"xwav-{kind}-{os.getuid()}"
        / key
    )


def request_action(
    request: dict,
    source: str,
    preview_source: str,
    *,
    kind: str = "preproduction",
    discover_checks=None,
    notice: str | None = None,
    source_fingerprint=None,
) -> dict:
    if kind not in {"preproduction", "loadtesting", "releases"}:
        raise ValueError("Unknown test report kind")
    get_version = source_fingerprint or fingerprint
    root = Path(request.get("workspace") or Path.cwd()).expanduser().resolve()
    if not root.is_dir() or root == Path("/") or root == Path.home():
        raise ValueError("Choose a project workspace, not a filesystem/home root.")
    directory = report_directory(root, request["session_id"], kind)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (directory / "lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        latest = directory / "latest"
        report_file = directory / f"{latest.read_text()}.json" if latest.exists() else None
        report = (
            json.loads(report_file.read_text()) if report_file and report_file.exists() else None
        )
        if report and report["state"] in {"complete", "cancelled"}:
            report["source_changed"] = (
                report.get("source_changed", False)
                or get_version(root) != report["source_version"]
            )
        if request["action"] == "cancel" and report:
            (directory / f"{report['id']}.cancel").touch()
        dead_worker = False
        if report and report["state"] == "running" and report.get("worker_pid"):
            try:
                os.kill(report["worker_pid"], 0)
                proc = Path(f"/proc/{report['worker_pid']}/cmdline")
                if proc.exists() and report["id"].encode() not in proc.read_bytes():
                    dead_worker = True
            except ProcessLookupError:
                dead_worker = True
        count_run = (
            kind == "loadtesting"
            and report
            and report.get("checks")
            and report["checks"][0].get("config", {}).get("request_mode") == "count"
        )
        expired = bool(report) and (
            time.time() - report.get("heartbeat_at", report["started_at"]) > 60
            if count_run
            else time.time() - report["started_at"]
            > (
                2800
                if kind == "releases" and report.get("checks", [{}])[0].get("engine") == "github"
                else 2400
                if kind == "loadtesting"
                else 1900
            )
        )
        if report and report["state"] == "running" and (dead_worker or expired):
            report.update(
                state="error",
                error=(
                    "Worker stopped reporting progress. Run again."
                    if count_run
                    else "Worker did not finish within its time limit. Run again."
                ),
            )
            assert report_file is not None
            save(report_file, report)
        if request["action"] in {"ensure", "start"} and (
            report is None or (request["action"] == "start" and report["state"] != "running")
        ):
            run_id = uuid.uuid4().hex
            report = {
                "id": run_id,
                "session_id": request["session_id"],
                "workspace": str(root),
                "state": "running",
                "started_at": time.time(),
                "source_version": get_version(root),
                "checks": (discover_checks or discover)(root),
                "notice": notice
                or (
                    "Existing suites plus limited browser/secret baselines. "
                    "Missing tooling and unconfigured categories are coverage "
                    "gaps, never passes. Responsive Android/iOS browser "
                    "checks are not native device certification."
                ),
            }
            save(directory / f"{run_id}.json", report)
            (directory / "runtime.py").write_text(source)
            (directory / "preview.py").write_text(preview_source)
            latest.write_text(run_id)
            with (directory / f"{run_id}.worker.log").open("wb") as log:
                subprocess.Popen(
                    [
                        sys.executable,
                        str(directory / "runtime.py"),
                        "--worker",
                        str(directory),
                        run_id,
                    ],
                    cwd=root,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )
        return report or {"state": "empty", "checks": []}


if __name__ == "__main__" and len(sys.argv) > 1:
    if sys.argv[1] == "--worker":
        worker(Path(sys.argv[2]), sys.argv[3])
    elif sys.argv[1] == "--audit":
        result = browser_audit(Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]))
        Path(sys.argv[5]).write_text(json.dumps(result))

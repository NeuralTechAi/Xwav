"""Real local builds and bounded release planning without publishing to accounts."""

import json
import os
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path

import pytest

from omnigent import preproduction_runtime as coordinator
from omnigent import release_runtime as release
from omnigent.server.releases import release_command


def configure(root, data):
    (root / ".xwav").mkdir(exist_ok=True)
    (root / ".xwav/release.json").write_text(json.dumps(data))


def worker(root, target="web", operation="build", provider="vercel", site="", execute=None):
    state = root.parent / (root.name + "-state")
    state.mkdir(exist_ok=True)
    plan = release.plan(root, target, operation, provider, site)
    report = {
        "id": uuid.uuid4().hex,
        "state": "running",
        "workspace": str(root),
        "checks": plan["steps"],
        "source_version": release.fingerprint(root),
    }
    coordinator.save(state / f"{report['id']}.json", report)
    release.worker(
        state, report["id"], coordinator.save, execute or coordinator.execute, release.fingerprint
    )
    return json.loads((state / f"{report['id']}.json").read_text())


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("XWAV_BUILD_CACHE", str(tmp_path / "tool-cache"))
    root = tmp_path / "app"
    root.mkdir()
    (root / "index.html").write_text('<script src="/app.js"></script>')
    (root / "app.js").write_text('console.log("app")')
    return root


def test_static_build_is_real_downloadable_zip_and_excludes_credentials(app):
    (app / ".env").write_text("SECRET=do-not-package")
    (app / "server.js").write_text("server backend")
    (app / "key.pem").write_text("private key")
    result = worker(app)
    assert result["state"] == "complete", result
    artifact = result["artifacts"][0]
    with zipfile.ZipFile(app / artifact["path"]) as archive:
        assert sorted(archive.namelist()) == ["app.js", "index.html"]
        assert archive.read("app.js") == b'console.log("app")'
    assert len(artifact["sha256"]) == 64
    assert not artifact["installable"]
    assert not (app / ".xwav/releases/work" / result["id"]).exists()
    assert sorted(p.name for p in (app / ".xwav/releases/artifacts" / result["id"]).iterdir()) == [
        "web.zip"
    ]


def test_web_copy_rejects_output_escape_and_ignores_outside_symlinks(app, tmp_path):
    outside = tmp_path / "secret.js"
    outside.write_text("secret")
    (app / "leak.js").symlink_to(outside)
    result = worker(app)
    with zipfile.ZipFile(app / result["artifacts"][0]["path"]) as archive:
        assert "leak.js" not in archive.namelist()
    configure(app, {"web_output": "../"})
    with pytest.raises(ValueError, match="inside"):
        release.config(app)


@pytest.mark.parametrize(
    "row",
    [
        {"build": "echo hi"},
        {"build": []},
        {"deploy": [1]},
        {"artifacts": ["../secret.exe"]},
        {"artifacts": ["/tmp/a.exe"]},
    ],
)
def test_invalid_configuration_never_runs(app, row):
    configure(app, {"targets": {"windows": row}})
    with pytest.raises(ValueError):
        release.plan(app, "windows", "build")


def test_native_readiness_offers_lazy_setup_without_downloading(app, monkeypatch):
    monkeypatch.setattr(release.platform, "system", lambda: "Linux")
    monkeypatch.setattr(release.shutil, "which", lambda name: None)
    monkeypatch.delenv("ANDROID_HOME", raising=False)
    monkeypatch.delenv("ANDROID_SDK_ROOT", raising=False)
    from unittest.mock import Mock

    fetch = Mock(side_effect=AssertionError("readiness must not download"))
    monkeypatch.setattr(release.release_tools, "download", fetch)
    assert release.plan(app, "android", "build")["ready"]
    assert release.plan(app, "android", "build")["android_licenses_required"]
    assert not release.plan(app, "ios", "build")["ready"]
    monkeypatch.setattr(release.release_tools, "wine_bootstrap_supported", lambda: True)
    assert release.plan(app, "windows", "build")["ready"]
    fetch.assert_not_called()


def test_configured_cloud_native_build_can_run_on_linux(app):
    configure(
        app,
        {
            "targets": {
                "android": {
                    "build": [
                        sys.executable,
                        "-c",
                        "from pathlib import Path; "
                        "import zipfile; "
                        "Path('build').mkdir(); "
                        "z=zipfile.ZipFile('build/app.apk','w'); "
                        "z.writestr('AndroidManifest.xml',b'\\x03\\x00\\x08\\x00'); "
                        "z.writestr('classes.dex',b'dex\\n'); "
                        "z.close()",
                    ],
                    "artifacts": ["build/*.apk"],
                }
            }
        },
    )
    result = worker(app, "android")
    assert result["state"] == "complete", result
    assert result["artifacts"][0]["name"] == "app.apk"
    assert result["artifacts"][0]["installable"]


def test_invalid_binary_is_not_an_installer(app):
    configure(
        app,
        {
            "targets": {
                "windows": {
                    "build": [
                        sys.executable,
                        "-c",
                        "from pathlib import Path; "
                        "Path('build').mkdir(); "
                        "Path('build/app.exe').write_text('not an exe')",
                    ],
                    "artifacts": ["build/*.exe"],
                }
            }
        },
    )
    result = worker(app, "windows")
    assert result["state"] == "error"
    assert result["artifacts"] == []


def test_failed_build_stops_before_publishing(app):
    configure(
        app,
        {
            "targets": {
                "web": {
                    "build": [sys.executable, "-c", "raise SystemExit(2)"],
                    "deploy": [sys.executable, "-c", "open('published','w').write('bad')"],
                }
            }
        },
    )
    result = worker(app, operation="deploy", provider="project")
    assert result["state"] == "error" and result["artifacts"] == []
    assert not (app / "published").exists()


@pytest.mark.parametrize(
    "provider,package",
    [
        ("vercel", "vercel"),
        ("netlify", "netlify-cli"),
        ("cloudflare", "wrangler"),
        ("railway", "@railway/cli"),
    ],
)
@pytest.mark.parametrize("channel", ["testing", "production"])
def test_provider_choice_reaches_real_command_plan_without_account_writes(
    app, monkeypatch, provider, package, channel
):
    monkeypatch.setenv("XWAV_RELEASE_CHANNEL", channel)
    monkeypatch.setenv("XWAV_STAGING_CONFIRMED", "true")
    monkeypatch.setenv("VERCEL_TOKEN", "test-secret-token")
    calls = []
    monkeypatch.setattr(release.release_tools, "prepare", lambda *a, **k: None)

    def execute(command, cwd, timeout, cancel, log):
        calls.append(command)
        return {
            "status": "passed",
            "output": "test-secret-token https://test.vercel.app",
            "duration": 0,
        }

    result = worker(app, operation="deploy", provider=provider, site="my-site", execute=execute)
    assert result["state"] == "complete", result
    assert any(package in command for command in calls)
    publish = next(command for command in calls if package in command)
    if provider in {"vercel", "netlify"}:
        assert ("--prod" in publish) == (channel == "production")
    if provider == "cloudflare":
        assert ("xwav-preview" in publish) == (channel == "testing")
    assert "test-secret-token" not in json.dumps(result)
    assert "[redacted]" in result["checks"][0]["output"]


def test_source_change_stops_deployment(app):
    configure(
        app,
        {
            "targets": {
                "web": {
                    "build": [sys.executable, "-c", "open('app.js','w').write('changed')"],
                    "deploy": ["true"],
                }
            }
        },
    )
    result = worker(app, operation="deploy", provider="project")
    assert result["state"] == "error" and "source changed" in result["error"]


def test_config_changes_mark_old_report_stale_but_outputs_do_not(app):
    configure(app, {"targets": {"web": {"build": ["true"]}}})
    old = release.fingerprint(app)
    (app / "dist").mkdir()
    (app / "dist/index.html").write_text("built output")
    assert release.fingerprint(app) == old
    configure(app, {"app_id": "app.xwav.example"})
    assert release.fingerprint(app) != old


def test_starting_page_only_returns_readiness_and_explicit_start_runs_worker(app, tmp_path):
    env = {**os.environ, "XWAV_TEST_REPORT_ROOT": str(tmp_path / "reports")}

    def request(action):
        result = subprocess.run(
            release_command("job", str(app), action),
            shell=True,
            capture_output=True,
            text=True,
            env=env,
            timeout=20,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout.strip().splitlines()[-1])

    status = request("status")
    assert status["state"] == "empty" and status["plans"][0]["ready"]
    started = request("start")
    assert started["state"] == "running"
    for _ in range(50):
        status = request("status")
        if status["state"] != "running":
            break
        time.sleep(0.1)
    assert status["state"] == "complete", status
    assert status["artifacts"]


@pytest.mark.parametrize("target", ["windows", "android", "ios"])
def test_conversion_generates_real_adapter_and_reuses_tools(app, monkeypatch, target):
    import plistlib

    monkeypatch.setattr(
        release.platform, "system", lambda: "Darwin" if target == "ios" else "Linux"
    )
    monkeypatch.setattr(release.shutil, "which", lambda name: f"/tools/{name}")
    monkeypatch.setenv("ANDROID_HOME", "/tools/android")
    (app / ".xwav").mkdir(exist_ok=True)
    (app / ".xwav/ExportOptions.plist").write_bytes(
        plistlib.dumps({"teamID": "TEAM123", "method": "development"})
    )
    configure(app, {"app_id": "com.example.fixture", "app_version": "2.3.4", "build_number": 42})
    calls = []
    monkeypatch.setattr(release.release_tools, "prepare", lambda *a, **k: None)

    def execute(command, cwd, timeout, cancel, log):
        calls.append(command)
        if command[:2] == ["npm", "install"]:
            (cwd / "node_modules").mkdir(exist_ok=True)
        elif "electron-builder" in command:
            destination = Path(
                next(
                    value.split("=", 1)[1]
                    for value in command
                    if value.startswith("-c.directories.output=")
                )
            )
            header = bytearray(128)
            header[:2] = b"MZ"
            header[60:64] = (64).to_bytes(4, "little")
            header[64:68] = b"PE\0\0"
            (destination / "App.exe").write_bytes(header)
        elif "cap" in command and "add" in command:
            (cwd / target).mkdir(exist_ok=True)
            if target == "android":
                (cwd / "android/app").mkdir()
                (cwd / "android/app/build.gradle").write_text('versionCode 1\nversionName "1.0"')
        elif command[:2] == ["sh", "gradlew"]:
            destination = cwd / "app/build/outputs/apk/debug/App.apk"
            destination.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(destination, "w") as archive:
                archive.writestr("AndroidManifest.xml", b"\x03\x00\x08\x00")
                archive.writestr("classes.dex", b"dex\n")
        elif "-exportArchive" in command:
            destination = Path(command[command.index("-exportPath") + 1]) / "App.ipa"
            with zipfile.ZipFile(destination, "w") as archive:
                archive.writestr("Payload/App.app/Info.plist", b"plist")
                archive.writestr("Payload/App.app/_CodeSignature/CodeResources", b"signature")
        return {"status": "passed", "output": "build adapter command passed"}

    result = worker(app, target, execute=execute)
    assert result["state"] == "complete", result
    assert result["artifacts"][0]["installable"]
    assert sum(command[:2] == ["npm", "install"] for command in calls) == 1
    result = worker(app, target, execute=execute)
    assert result["state"] == "complete", result
    assert sum(command[:2] == ["npm", "install"] for command in calls) == 1
    adapter = app / ".xwav/releases/adapters/app-state" / target
    assert (adapter / "www/index.html").exists()
    manifest = json.loads((adapter / "package.json").read_text())
    assert manifest["version"] == "2.3.4"
    if target == "android":
        assert "versionCode 42" in (adapter / "android/app/build.gradle").read_text()
        assert 'versionName "2.3.4"' in (adapter / "android/app/build.gradle").read_text()
    if target == "windows":
        assert "protocol.handle" in (adapter / "main.cjs").read_text()
    if target == "ios":
        assert any("DEVELOPMENT_TEAM=TEAM123" in command for command in calls)


def test_provider_source_staging_excludes_local_runtime_and_signing_files(app):
    (app / "server.js").write_text("backend source")
    (app / ".env").write_text("TOKEN=private")
    (app / "key.pem").write_text("signing key")
    (app / ".xwav").mkdir()
    (app / ".xwav/private.json").write_text("job metadata")
    (app / ".vercel").mkdir()
    (app / ".vercel/project.json").write_text('{"projectId":"linked"}')
    (app / "node_modules").mkdir()
    (app / "node_modules/tool.js").write_text("cache")
    destination = app / ".xwav/upload"
    release.stage_source(app, destination)
    files = sorted(
        str(path.relative_to(destination)) for path in destination.rglob("*") if path.is_file()
    )
    assert files == [".vercel/project.json", "app.js", "index.html", "server.js"]


@pytest.mark.parametrize("provider", ["vercel", "railway"])
def test_fullstack_provider_builds_staged_backend_source(app, provider):
    (app / "index.html").unlink()
    (app / "package.json").write_text('{"scripts":{"start":"node server.js"}}')
    (app / "server.js").write_text("backend source")
    (app / ".env").write_text("TOKEN=private")
    paths = []

    def execute(command, cwd, timeout, cancel, log):
        index = command.index("deploy" if provider == "vercel" else "up")
        upload = Path(command[index + 1])
        paths.append(upload)
        assert (upload / "server.js").read_text() == "backend source"
        assert not (upload / ".env").exists()
        assert not (upload / ".xwav").exists()
        if provider == "vercel":
            link = upload / ".vercel/project.json"
            if link.exists():
                assert json.loads(link.read_text())["projectId"] == "selected-project"
            link.parent.mkdir(exist_ok=True)
            link.write_text('{"projectId":"selected-project","orgId":"selected-org"}')
        return {"status": "passed", "output": "source deployment completed"}

    result = worker(app, operation="deploy", provider=provider, execute=execute)
    assert result["state"] == "complete", result
    assert result["artifacts"] == []
    result = worker(app, operation="deploy", provider=provider, execute=execute)
    assert result["state"] == "complete", result
    assert paths[0].name == paths[1].name
    assert paths[0].parent != paths[1].parent


def test_source_fingerprint_ignores_mtime_only_changes(app):
    before = release.fingerprint(app)
    (app / "app.js").touch()
    assert release.fingerprint(app) == before
    (app / "app.js").write_text("changed source")
    assert release.fingerprint(app) != before


def test_worker_transport_fits_shell_argument_limits(app):
    assert len(release_command("job", str(app), "status").encode()) < 65536


def test_static_export_changes_are_tracked_and_configured_artifacts_are_not(app):
    (app / "public").mkdir()
    (app / "public/index.html").write_text("static frontend")
    configure(
        app, {"web_output": "public", "targets": {"android": {"artifacts": ["artifacts/*.apk"]}}}
    )
    old = release.fingerprint(app)
    (app / "public/index.html").write_text("changed frontend")
    changed = release.fingerprint(app)
    assert changed != old
    (app / "artifacts").mkdir()
    (app / "artifacts/app.apk").write_bytes(b"build output")
    assert release.fingerprint(app) == changed


def test_prebuilt_dist_is_source_when_no_browser_build_is_configured(app):
    (app / "dist").mkdir()
    (app / "dist/index.html").write_text("prebuilt app")
    old = release.fingerprint(app)
    (app / "dist/index.html").write_text("new prebuilt app")
    assert release.fingerprint(app) != old


def test_android_start_requires_licence_before_creating_worker(app, tmp_path, monkeypatch):
    monkeypatch.setenv("ANDROID_HOME", str(tmp_path / "empty-sdk"))
    monkeypatch.setenv("ANDROID_SDK_ROOT", str(tmp_path / "empty-sdk"))
    command = release_command("android-licence", str(app), "start", target="android")
    result = subprocess.run(["sh", "-c", command], capture_output=True, text=True, timeout=15)
    report = json.loads(result.stdout)
    assert report["state"] == "error"
    assert "licence" in report["error"]
    assert not (app / ".xwav/releases").exists()


def test_prebuilt_frontend_and_web_specific_build_are_detected(app):
    (app / "index.html").unlink()
    (app / "dist").mkdir()
    (app / "dist/index.html").write_text("prebuilt")
    assert release.plan(app, "web", "build")["ready"]
    assert worker(app)["state"] == "complete"
    (app / "package.json").write_text(json.dumps({"scripts": {"build:web": "echo web"}}))
    assert release.web_build(app) == ["npm", "run", "build:web"]
    assert release.plan(app, "android", "build")["ready"]


def test_changed_source_cannot_reuse_an_unchanged_native_package(app):
    configure(
        app,
        {
            "targets": {
                "android": {
                    "build": [
                        sys.executable,
                        "-c",
                        "from pathlib import Path; import zipfile; "
                        "Path('build').mkdir(exist_ok=True); p=Path('build/app.apk'); "
                        "z=zipfile.ZipFile(p,'w') if not p.exists() else None; "
                        "z.writestr('AndroidManifest.xml',b'xml') if z else None; "
                        "z.writestr('classes.dex',b'dex') if z else None; "
                        "z.close() if z else None",
                    ],
                    "artifacts": ["build/*.apk"],
                }
            }
        },
    )
    assert worker(app, "android")["state"] == "complete"
    (app.parent / (app.name + "-state") / "corrupt-old-report.json").write_text("invalid report")
    assert worker(app, "android")["state"] == "complete"
    (app / "app.js").write_text("changed source")
    result = worker(app, "android")
    assert result["state"] == "error" and not result["artifacts"]
    assert "new or updated" in result["error"]


@pytest.mark.parametrize("tamper", ["none", "changed", "symlink", "truncated"])
def test_download_verifies_actual_package_bytes(app, tamper):
    import hashlib

    from omnigent.server.releases import artifact_verification_command

    file = app / "app.exe"
    content = b"verified package bytes"
    file.write_bytes(content)
    command = artifact_verification_command(
        str(app), "app.exe", len(content), hashlib.sha256(content).hexdigest()
    )
    if tamper == "changed":
        file.write_bytes(b"x" * len(content))
    elif tamper == "symlink":
        real = app / "other.exe"
        file.rename(real)
        file.symlink_to(real)
    elif tamper == "truncated":
        file.write_bytes(b"short")
    output = subprocess.run(command, shell=True, text=True, capture_output=True, timeout=10)
    assert json.loads(output.stdout)["valid"] is (tamper == "none")


def test_status_streams_logs_and_invalid_config_does_not_prevent_cancellation(
    app, tmp_path, monkeypatch
):
    monkeypatch.setenv("RELEASE_TEST_TOKEN", "private-release-test-key")
    configure(
        app,
        {
            "targets": {
                "web": {
                    "build": [
                        sys.executable,
                        "-u",
                        "-c",
                        "import time,os; print('BUILD IS RUNNING',"
                        "os.environ['RELEASE_TEST_TOKEN'],flush=True); time.sleep(30)",
                    ]
                }
            }
        },
    )
    env = {**os.environ, "XWAV_TEST_REPORT_ROOT": str(tmp_path / "reports")}

    def request(action):
        result = subprocess.run(
            release_command("cancel-test", str(app), action),
            shell=True,
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        return json.loads(result.stdout)

    request("start")
    try:
        for _ in range(50):
            report = request("status")
            if "BUILD IS RUNNING" in report.get("checks", [{}])[0].get("live_output", ""):
                break
            time.sleep(0.1)
        assert report["state"] == "running"
        assert "BUILD IS RUNNING" in report["checks"][0]["live_output"]
        assert "private-release-test-key" not in json.dumps(report)
        assert "[redacted]" in report["checks"][0]["live_output"]
        (app / ".xwav/release.json").write_text("invalid JSON")
        request("cancel")
        for _ in range(50):
            report = request("status")
            if report["state"] != "running":
                break
            time.sleep(0.1)
        assert report["state"] == "cancelled", report
        assert not report["plans"][0]["ready"]
    finally:
        request("cancel")


def test_project_relative_build_executable_runs_in_workspace(app):
    executable = app / "build.py"
    executable.write_text(
        "#!/usr/bin/env python3\nfrom pathlib import Path\n"
        "Path('dist').mkdir(exist_ok=True)\n"
        "Path('dist/index.html').write_text('<h1>relative build</h1>')\n"
    )
    executable.chmod(0o755)
    configure(app, {"targets": {"web": {"build": ["./build.py"]}}})
    assert release.plan(app, "web", "build")["ready"]
    result = worker(app)
    assert result["state"] == "complete", result

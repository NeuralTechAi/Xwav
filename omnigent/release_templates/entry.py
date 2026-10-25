"""Run the bundled Xwav release engine in an ephemeral cloud worker."""

import base64
import importlib.util
import json
import os
import plistlib
import secrets
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from types import ModuleType


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load release module: {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def command(args):
    # Signing commands can contain passwords. Never echo command lines or tool errors.
    result = subprocess.run(args, capture_output=True, timeout=120)
    if result.returncode:
        raise RuntimeError(
            f"Signing setup failed: {args[0]}. Check signing credentials and profile."
        )
    return result.stdout


def private_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(0o600)
    return str(path)


def main():
    sys.dont_write_bytecode = True
    root = Path.cwd()
    folder = root / ".xwav/cloud"
    namespace = ModuleType("omnigent")
    sys.modules["omnigent"] = namespace
    namespace.__dict__["release_tools"] = load(
        "omnigent.release_tools", folder / "release_tools.py"
    )
    runtime = load("omnigent.release_runtime", folder / "release_runtime.py")
    coordinator = load("xwav_coordinator", folder / "coordinator.py")
    request = json.loads(os.environ["XWAV_REQUEST"])
    target, operation = request["target"], request["operation"]
    source_sha = command(["git", "rev-parse", "HEAD"]).decode().strip()
    if source_sha != request["source_sha"]:
        raise ValueError("Worker checkout does not match the requested commit")
    channel = request.get("channel", "testing")
    os.environ["XWAV_RELEASE_CHANNEL"] = channel
    if channel not in {"testing", "production"}:
        raise ValueError("Invalid release channel")
    if target == "android" and request.get("accept_android_licenses") not in {True, "true"}:
        raise ValueError("Accept the Android SDK licences in Xwav before starting")
    cfg = runtime.config(root)
    original = root / ".xwav/release.json"
    original_bytes = original.read_bytes() if original.exists() else None
    keychain = None
    previous_keychains = []
    profile = None
    export_options = root / ".xwav/ExportOptions.plist"
    previous_export = export_options.read_bytes() if export_options.exists() else None
    with tempfile.TemporaryDirectory(prefix="xwav-signing-") as temporary:
        secret_dir = Path(temporary)
        try:
            if target == "android" and operation == "deploy":
                required = ["KEYSTORE_B64", "KEYSTORE_PASSWORD", "KEY_ALIAS", "KEY_PASSWORD"]
                for suffix in required:
                    if not os.environ.get("XWAV_ANDROID_" + suffix):
                        raise ValueError("Missing Android signing secret: XWAV_ANDROID_" + suffix)
                keyfile = private_file(
                    secret_dir / "upload.jks",
                    base64.b64decode(os.environ["XWAV_ANDROID_KEYSTORE_B64"], validate=True),
                )
                init = secret_dir / "sign.gradle"
                init.write_text("""allprojects { project ->
    afterEvaluate {
        if (project.plugins.hasPlugin('com.android.application')) {
            project.android.signingConfigs.create('xwavUpload') {
                storeFile new File(System.getenv('XWAV_ANDROID_KEYSTORE_PATH'))
                storePassword System.getenv('XWAV_ANDROID_KEYSTORE_PASSWORD')
                keyAlias System.getenv('XWAV_ANDROID_KEY_ALIAS')
                keyPassword System.getenv('XWAV_ANDROID_KEY_PASSWORD')
            }
            project.android.buildTypes.release.signingConfig =
                project.android.signingConfigs.xwavUpload
        }
    }
}
""")
                os.environ["XWAV_ANDROID_KEYSTORE_PATH"] = keyfile
                gradle_home = secret_dir / "gradle"
                (gradle_home / "init.d").mkdir(parents=True)
                shutil.copyfile(init, gradle_home / "init.d/xwav.gradle")
                os.environ["GRADLE_USER_HOME"] = str(gradle_home)
            if target == "ios":
                for name in [
                    "XWAV_IOS_CERTIFICATE_B64",
                    "XWAV_IOS_PROFILE_B64",
                    "XWAV_IOS_EXPORT_OPTIONS_B64",
                ]:
                    if not os.environ.get(name):
                        raise ValueError("Missing iOS signing secret: " + name)
                certificate = private_file(
                    secret_dir / "sign.p12",
                    base64.b64decode(os.environ["XWAV_IOS_CERTIFICATE_B64"], validate=True),
                )
                keychain = str(secret_dir / "signing.keychain-db")
                password = secrets.token_hex(24)
                previous_keychains = (
                    command(["security", "list-keychains", "-d", "user"])
                    .decode()
                    .replace('"', "")
                    .split()
                )
                command(["security", "create-keychain", "-p", password, keychain])
                command(["security", "set-keychain-settings", "-lut", "21600", keychain])
                command(["security", "unlock-keychain", "-p", password, keychain])
                command(
                    [
                        "security",
                        "import",
                        certificate,
                        "-P",
                        os.environ.get("XWAV_IOS_CERTIFICATE_PASSWORD", ""),
                        "-A",
                        "-t",
                        "cert",
                        "-f",
                        "pkcs12",
                        "-k",
                        keychain,
                    ]
                )
                command(
                    [
                        "security",
                        "set-key-partition-list",
                        "-S",
                        "apple-tool:,apple:,codesign:",
                        "-k",
                        password,
                        keychain,
                    ]
                )
                command(
                    [
                        "security",
                        "list-keychains",
                        "-d",
                        "user",
                        "-s",
                        keychain,
                        *previous_keychains,
                    ]
                )
                raw_profile = base64.b64decode(os.environ["XWAV_IOS_PROFILE_B64"], validate=True)
                temporary_profile = private_file(
                    secret_dir / "profile.mobileprovision", raw_profile
                )
                details = plistlib.loads(
                    command(["security", "cms", "-D", "-i", temporary_profile])
                )
                os.environ["XWAV_IOS_PROFILE_NAME"] = details["Name"]
                profile_id = str(uuid.UUID(details["UUID"]))
                profile = (
                    Path.home()
                    / "Library/MobileDevice/Provisioning Profiles"
                    / (profile_id + ".mobileprovision")
                )
                private_file(profile, raw_profile)
                private_file(
                    export_options,
                    base64.b64decode(os.environ["XWAV_IOS_EXPORT_OPTIONS_B64"], validate=True),
                )
            if operation == "deploy" and target != "web":
                if not cfg.get("build_number"):
                    raise ValueError("Set a unique positive build_number in .xwav/release.json")
                row = cfg.setdefault("targets", {}).setdefault(target, {})
                if not row.get("deploy") and not runtime.script(root, f"deploy:{target}"):
                    row["deploy"] = [sys.executable, str(folder / "publish.py"), target, channel]
                original.write_text(json.dumps(cfg))
            provider = request.get("provider", "vercel")
            selected = runtime.plan(root, target, operation, provider, request.get("site", ""))
            if not selected["ready"]:
                raise ValueError(selected["reason"])
            state = root / ".xwav/cloud-state"
            state.mkdir(exist_ok=True)
            run_id = uuid.uuid4().hex
            selected["steps"][0]["accept_android_licenses"] = True
            report = {
                "id": run_id,
                "workspace": str(root),
                "source_version": runtime.fingerprint(root),
                "state": "running",
                "checks": selected["steps"],
            }
            coordinator.save(state / f"{run_id}.json", report)
            runtime.worker(
                state, run_id, coordinator.save, coordinator.execute, runtime.fingerprint
            )
            report = json.loads((state / f"{run_id}.json").read_text())
            if report["state"] != "complete":
                print(runtime.redact(report["checks"][0].get("output", "")), flush=True)
                print(runtime.redact(report.get("error", "Cloud build failed")), flush=True)
                raise RuntimeError(report.get("error", "Cloud build failed"))
            destination = root / ".xwav/cloud-export"
            destination.mkdir(exist_ok=True)
            for artifact in report["artifacts"]:
                shutil.copyfile(root / artifact["path"], destination / artifact["name"])
            manifest = {
                "commit": source_sha,
                "target": target,
                "operation": operation,
                "channel": channel,
                "artifacts": report["artifacts"],
                "urls": report.get("urls", []),
            }
            (destination / "manifest.json").write_text(json.dumps(manifest))
        finally:
            if keychain:
                command(["security", "list-keychains", "-d", "user", "-s", *previous_keychains])
                command(["security", "delete-keychain", keychain])
            if profile:
                profile.unlink(missing_ok=True)
            if previous_export is not None:
                export_options.write_bytes(previous_export)
            elif target == "ios":
                export_options.unlink(missing_ok=True)
            if original_bytes is not None:
                original.write_bytes(original_bytes)
            else:
                original.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        RuntimeError,
        subprocess.SubprocessError,
    ) as error:
        # Never dump signing values or subprocess arguments in CI logs.
        print(
            f"Xwav cloud release failed: {type(error).__name__}. "
            "Review the release setup and worker logs.",
            flush=True,
        )
        sys.exit(1)

"""Store upload adapter. Credentials exist only in the cloud worker's temp directory."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def publish(root, target, channel):
    if target not in {"android", "ios"} or channel not in {"testing", "production"}:
        raise ValueError("Unsupported store target or channel")
    # Runtime invokes this after recording verified packages and before marking success.
    reports = list((root / ".xwav/cloud-state").glob("*.json"))
    if len(reports) != 1:
        raise ValueError("Expected exactly one cloud release report")
    report = json.loads(reports[0].read_text())
    suffix = ".aab" if target == "android" else ".ipa"
    packages = [
        root / row["path"] for row in report.get("artifacts", []) if row["name"].endswith(suffix)
    ]
    if len(packages) != 1:
        raise ValueError("Expected one signed store package")
    with tempfile.TemporaryDirectory(prefix="xwav-store-") as temporary:
        credentials = Path(temporary) / "credentials.json"
        name = "XWAV_GOOGLE_PLAY_JSON" if target == "android" else "XWAV_APPLE_API_JSON"
        value = os.environ.get(name)
        if not value:
            raise ValueError("Missing store credential: " + name)
        json.loads(value)
        credentials.write_text(value)
        credentials.chmod(0o600)
        if target == "android":
            verified = subprocess.run(
                ["jarsigner", "-verify", str(packages[0])],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if verified.returncode or "jar verified" not in verified.stdout.lower():
                raise ValueError("Google Play requires a signed Android bundle")
            config = json.loads((root / ".xwav/release.json").read_text())
            command = [
                "fastlane",
                "run",
                "upload_to_play_store",
                f"json_key:{credentials}",
                f"aab:{packages[0]}",
                f"package_name:{config['app_id']}",
                "track:" + ("internal" if channel == "testing" else "production"),
                "release_status:completed",
                "skip_upload_metadata:true",
                "skip_upload_images:true",
                "skip_upload_screenshots:true",
            ]
        else:
            command = [
                "fastlane",
                "run",
                "upload_to_testflight" if channel == "testing" else "upload_to_app_store",
                f"api_key_path:{credentials}",
                f"ipa:{packages[0]}",
            ]
            command += (
                ["distribute_external:false"]
                if channel == "testing"
                else [
                    "skip_metadata:true",
                    "skip_screenshots:true",
                    "submit_for_review:false",
                    "force:true",
                ]
            )
        subprocess.run(command, check=True, timeout=1200)


if __name__ == "__main__":
    publish(Path.cwd(), *sys.argv[1:])

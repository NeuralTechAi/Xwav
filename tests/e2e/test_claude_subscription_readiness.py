"""Selected Claude subscription readiness across the host process boundary."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

from omnigent._platform import resolve_cli_binary
from tests._helpers.host import isolated_host
from tests._helpers.live_server import isolated_local_server, isolated_process_env
from tests._helpers.polling import poll_until


def _check_host_readiness(root: Path, background: bool, subscription_login: bool = False) -> None:
    base_env = {
        name: os.environ[name]
        for name in ("PATH", "LANG", "OMNIGENT_HARNESS_TMP_PARENT")
        if name in os.environ
    }
    host_root = root / "host"
    home = host_root / "home"
    home.mkdir(parents=True)
    overrides = {
        "CLAUDE_CONFIG_DIR": str(home / ".claude"),
        "DISABLE_TELEMETRY": "1",
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_ERROR_REPORTING": "1",
    }
    if subscription_login:
        credential = home / ".claude" / ".credentials.json"
        credential.parent.mkdir()
        credential.write_text(
            json.dumps(
                {
                    "claudeAiOauth": {
                        "accessToken": "synthetic-subscription-access-token",
                        "expiresAt": 99999999999999,
                        "scopes": ["user:inference", "user:profile"],
                        "subscriptionType": "max",
                    }
                }
            )
        )
    else:
        overrides["ANTHROPIC_API_KEY"] = "synthetic-not-a-real-key"
    env = isolated_process_env(
        home, {**overrides, "OMNIGENT_CONFIG_HOME": str(home / ".omnigent")}, base_env
    )
    version = subprocess.run(
        ["claude", "--version"], env=env, capture_output=True, text=True, timeout=15, check=True
    )
    status = subprocess.run(
        ["claude", "auth", "status"],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    auth = json.loads(status.stdout)
    (root / "claude-auth.json").write_text(
        json.dumps({"version": version.stdout.strip(), "status": auth}, indent=2)
    )
    expected_auth = "claude.ai" if subscription_login else "api_key"
    assert auth["loggedIn"] is True and auth["authMethod"] == expected_auth, auth
    config = {
        "providers": {"selected": {"kind": "subscription", "cli": "claude", "default": True}}
    }
    prefix = [sys.executable, "-m", "omnigent"]
    with (
        isolated_local_server(root / "server", base_env=base_env) as base_url,
        httpx.Client(base_url=base_url, trust_env=False, timeout=3) as client,
    ):
        command = [*prefix, "host", "--server", base_url, "--non-interactive", "--no-open"]
        if background:
            command.append("--background")
        (root / "host-command.json").write_text(json.dumps(command, indent=2))
        with isolated_host(
            host_root,
            base_url,
            config=config,
            env=overrides,
            base_env=base_env,
            command=command,
            cwd=home,
        ) as host:
            try:
                if background:
                    assert host.proc.wait(timeout=75) == 0, host.log_path.read_text()

                def online() -> dict[str, Any] | None:
                    response = client.get("/v1/hosts")
                    response.raise_for_status()
                    return next(
                        (
                            row
                            for row in response.json()["hosts"]
                            if row["host_id"] == host.host_id and row["status"] == "online"
                        ),
                        None,
                    )

                poll_until(online, timeout_s=60)
                advertisement = online()
                assert advertisement is not None
                (root / "host-advertisement.json").write_text(json.dumps(advertisement, indent=2))
                expected_readiness = True if subscription_login else "needs-auth"
                for harness in ("claude-native", "claude-sdk"):
                    assert advertisement["configured_harnesses"][harness] == expected_readiness
            finally:
                stop = subprocess.run(
                    [*prefix, "host", "stop", "--server", base_url, "--force"],
                    env=env,
                    cwd=home,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                (root / "host-stop.txt").write_text(stop.stdout + stop.stderr)
                assert stop.returncode == 0, stop.stderr


@pytest.mark.skipif(
    not sys.platform.startswith("linux") or shutil.which("bwrap") is None,
    reason="Requires bubblewrap network, PID, and managed-settings isolation",
)
@pytest.mark.parametrize("background", [False, True], ids=["foreground", "background"])
@pytest.mark.parametrize("subscription_login", [False, True], ids=["api-only", "stored-login"])
@pytest.mark.timeout(210)
def test_selected_subscription_host_readiness(
    tmp_path: Path, background: bool, subscription_login: bool
) -> None:
    if resolve_cli_binary("claude") is None:
        pytest.skip("Requires installed Claude CLI")
    base_env = {name: os.environ[name] for name in ("PATH", "LANG") if name in os.environ}
    env = isolated_process_env(
        tmp_path / "driver-home",
        {"OMNIGENT_HARNESS_TMP_PARENT": str(tmp_path / "harness-tmp")},
        base_env,
    )
    result = subprocess.run(
        [
            "bwrap",
            "--bind",
            "/",
            "/",
            "--dev",
            "/dev",
            "--proc",
            "/proc",
            "--unshare-net",
            "--unshare-pid",
            "--die-with-parent",
            "--tmpfs",
            "/etc/claude-code",
            "--",
            sys.executable,
            "-c",
            "from pathlib import Path; "
            "from tests.e2e.test_claude_subscription_readiness import _check_host_readiness; "
            f"_check_host_readiness(Path({str(tmp_path)!r}), "
            f"{background!r}, {subscription_login!r})",
        ],
        env=env,
        cwd=tmp_path,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=200,
        check=False,
    )
    (tmp_path / "driver.txt").write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr

"""Local, per-job Docker containers using the shared managed-host lifecycle."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import ClassVar, Literal

import click
from pydantic import BaseModel, ConfigDict, Field, field_validator

from omnigent.onboarding.sandboxes.base import RemoteCommandResult, SandboxLauncher

_LABEL = "ai.xwav.managed"


class DockerSandboxConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image: str = Field(default="xwav-host:local", min_length=1)
    cpus: float = Field(default=2, gt=0, le=64)
    memory_mib: int = Field(default=2048, ge=256)
    pids_limit: int = Field(default=512, ge=32)
    network: Literal["host", "bridge"] = "host"
    env: list[str] = Field(default_factory=list)
    inherit_codex_login: bool = False

    @field_validator("env")
    @classmethod
    def validate_environment_names(cls, names: list[str]) -> list[str]:
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) for name in names):
            raise ValueError("Docker sandbox env entries must be environment variable names")
        return names


class DockerSandboxLauncher(SandboxLauncher):
    provider: ClassVar[str] = "docker"
    supports_cli_bootstrap: ClassVar[bool] = False

    def __init__(self, *, config: DockerSandboxConfig | None = None) -> None:
        self.config = config or DockerSandboxConfig()

    def _docker(self, *args: str, command: str | None = None) -> RemoteCommandResult:
        try:
            result = subprocess.run(
                ["docker", *args],
                input=command,
                text=True,
                capture_output=True,
                timeout=300,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise click.ClickException("Docker sandbox command failed or timed out") from exc
        return RemoteCommandResult(result.returncode, result.stdout, result.stderr)

    @staticmethod
    def _check(result: RemoteCommandResult) -> RemoteCommandResult:
        if result.returncode:
            raise click.ClickException(f"Docker sandbox command failed: {result.stderr[-2000:]}")
        return result

    def prepare(self) -> None:
        if shutil.which("docker") is None:
            raise click.ClickException("Install and start Docker to run isolated project jobs")
        self._check(self._docker("info", "--format", "{{.ServerVersion}}"))
        if self._docker("image", "inspect", self.config.image).returncode:
            raise click.ClickException(
                f"Sandbox image {self.config.image!r} is missing. Build the host image with "
                "docker build --target host -t xwav-host:local -f deploy/docker/Dockerfile ."
            )

    def provision(self, name: str) -> str:
        args = [
            "run",
            "--detach",
            "--rm",
            "--init",
            "--name",
            f"xwav-job-{uuid.uuid4().hex}",
            "--label",
            f"{_LABEL}=true",
            "--label",
            f"ai.xwav.job={name}",
            "--user",
            "sandbox",
            "--workdir",
            "/sandbox",
            "--env",
            "HOME=/sandbox",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit",
            str(self.config.pids_limit),
            "--cpus",
            str(self.config.cpus),
            "--memory",
            f"{self.config.memory_mib}m",
            "--network",
            self.config.network,
            "--add-host",
            "host.docker.internal:host-gateway",
        ]
        for key in self.config.env:
            if key in os.environ:
                args.extend(["--env", key])
        args.extend([self.config.image, "sleep", "infinity"])
        sandbox_id = self._check(self._docker(*args)).stdout.strip()
        if self.config.inherit_codex_login:
            try:
                self.install_codex_login(sandbox_id)
            except Exception:
                self.terminate(sandbox_id)
                raise
        return sandbox_id

    def install_codex_login(self, sandbox_id: str) -> None:
        """Copy an explicitly enabled local Codex login through stdin, never a mount."""
        from omnigent.onboarding.ambient import codex_auth_has_credential

        if not self.config.inherit_codex_login:
            raise click.ClickException("Codex login inheritance is not enabled")
        if not self._owned(sandbox_id):
            raise click.ClickException("Docker sandbox no longer exists")
        source = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
        if not codex_auth_has_credential(source):
            raise click.ClickException(
                "Sign in with codex login on the server before creating a job"
            )
        script = (
            "import os,sys,tempfile; from pathlib import Path; "
            "directory=Path('/sandbox/.codex'); directory.mkdir(mode=0o700,exist_ok=True); "
            "os.chmod(directory,0o700); path=directory/'auth.json'; "
            "fd,name=tempfile.mkstemp(dir=directory); "
            "os.fchmod(fd,0o600); "
            "handle=os.fdopen(fd,'w'); handle.write(sys.stdin.read()); handle.close(); "
            "os.replace(name,path)"
        )
        self._check(
            self._docker(
                "exec",
                "--interactive",
                sandbox_id,
                "python3",
                "-c",
                script,
                command=source.read_text(encoding="utf-8"),
            )
        )

    def _owned(self, sandbox_id: str) -> bool:
        if not re.fullmatch(r"[0-9a-f]{64}", sandbox_id):
            raise click.ClickException("Invalid Docker sandbox id")
        result = self._docker(
            "inspect",
            "--format",
            '{{ index .Config.Labels "ai.xwav.managed" }}',
            sandbox_id,
        )
        if result.returncode:
            if "No such" in result.stderr:
                return False
            self._check(result)
        if result.stdout.strip() != "true":
            raise click.ClickException("Container is not an Xwav managed sandbox")
        return True

    def run(self, sandbox_id: str, command: str, *, check: bool = True) -> RemoteCommandResult:
        if not self._owned(sandbox_id):
            raise click.ClickException("Docker sandbox no longer exists")
        # Bootstrap commands can carry a launch token; pass them on stdin, not argv.
        result = self._docker("exec", "--interactive", sandbox_id, "sh", "-s", command=command)
        return self._check(result) if check else result

    def terminate(self, sandbox_id: str) -> None:
        if self._owned(sandbox_id):
            self._check(self._docker("rm", "--force", sandbox_id))

"""Transport release planning/builds to existing runners without a runner upgrade."""

import base64
import json
import zlib
from pathlib import Path

from omnigent import preproduction_runtime, release_cloud, release_runtime, release_tools


def release_command(
    session_id: str,
    workspace: str | None,
    action: str,
    *,
    target: str = "web",
    operation: str = "build",
    provider: str = "vercel",
    site: str = "",
    accept_android_licenses: bool = False,
    engine: str = "local",
    channel: str = "testing",
    repository: str = "",
) -> str:
    if (
        action not in {"status", "start", "cancel", "prepare", "verify"}
        or engine not in {"local", "github"}
        or channel not in {"testing", "production"}
        or target not in release_runtime.TARGETS
        or operation not in {"build", "deploy"}
        or provider not in release_runtime.PROVIDERS
    ):
        raise ValueError("Invalid release request")
    if action in {"prepare", "verify"} and engine != "github":
        raise ValueError("Choose GitHub Actions for cloud setup")
    if not isinstance(repository, str) or len(repository) > 200:
        raise ValueError("Invalid GitHub repository")
    if not isinstance(accept_android_licenses, bool):
        raise ValueError("Android licence acceptance must be a boolean")
    coordinator = Path(preproduction_runtime.__file__).read_text()
    runtime = (
        Path(release_runtime.__file__)
        .read_text()
        .replace("from omnigent import release_tools", "")
    )
    tools_blob = base64.b64encode(
        zlib.compress(Path(release_tools.__file__).read_bytes(), 9)
    ).decode()
    coordinator_blob = base64.b64encode(zlib.compress(coordinator.encode(), 9)).decode()
    runtime_blob = base64.b64encode(zlib.compress(runtime.encode(), 9)).decode()
    cloud_blob = base64.b64encode(
        zlib.compress(Path(release_cloud.__file__).read_bytes(), 9)
    ).decode()
    cloud_source = (
        "cloud={'__name__':'xwav_cloud'}\n"
        f"exec(zlib.decompress(base64.b64decode({cloud_blob!r})),cloud)\n"
        if engine == "github"
        else ""
    )
    source = (
        "import sys,json,zlib,base64; from pathlib import Path\n"
        "coordinator={'__name__':'xwav_coordinator'}\n"
        f"exec(zlib.decompress(base64.b64decode({coordinator_blob!r})),coordinator)\n"
        "from types import SimpleNamespace\n"
        "toolchain={'__name__':'xwav_release_tools'}\n"
        f"exec(zlib.decompress(base64.b64decode({tools_blob!r})),toolchain)\n"
        "release={'__name__':'xwav_release','release_tools':SimpleNamespace(**toolchain)}\n"
        f"exec(zlib.decompress(base64.b64decode({runtime_blob!r})),release)\n"
        + cloud_source
        + "if len(sys.argv)>1 and sys.argv[1]=='--worker':\n"
        + (
            "    cloud['worker'](Path(sys.argv[2]),sys.argv[3],"
            "coordinator['save'],coordinator['execute'],release['fingerprint'],"
            "SimpleNamespace(**release))\n"
            if engine == "github"
            else "    release['worker'](Path(sys.argv[2]),sys.argv[3],"
            "coordinator['save'],coordinator['execute'],release['fingerprint'])\n"
        )
    )
    request = {"session_id": session_id, "workspace": workspace, "action": action}
    source_blob = base64.b64encode(zlib.compress(source.encode(), 9)).decode()
    bootstrap = (
        "import base64,zlib\n"
        f"_source=zlib.decompress(base64.b64decode({source_blob!r})).decode()\n"
        "exec(_source)\n"
    )
    if engine == "github":
        template_dir = Path(release_cloud.__file__).parent / "release_templates"
        files = (
            {
                ".github/workflows/xwav-release.yml": (template_dir / "workflow.yml").read_text(),
                **{
                    f".xwav/cloud/{name}": (template_dir / name).read_text()
                    for name in ("entry.py", "publish.py")
                },
                ".xwav/cloud/release_runtime.py": Path(release_runtime.__file__).read_text(),
                ".xwav/cloud/release_tools.py": Path(release_tools.__file__).read_text(),
                ".xwav/cloud/coordinator.py": coordinator,
            }
            if action == "prepare"
            else {}
        )
        if action == "prepare":
            payload = base64.b64encode(zlib.compress(json.dumps(files).encode(), 9)).decode()
            code = (
                "import json,base64,zlib\nfrom pathlib import Path\n"
                + cloud_source
                + f"root=Path({workspace!r} or Path.cwd()).expanduser().resolve()\n"
                + "try:\n"
                + f"    files=json.loads(zlib.decompress(base64.b64decode({payload!r})))\n"
                + f"    message=cloud['prepare'](root,{repository!r},files)\n"
                + "    print(json.dumps({'state':'empty','checks':[],'artifacts':[],"
                + f"'cloud':{{'repository':{repository!r},'message':message}}}}))\n"
                + "except Exception as exc:\n"
                + "    print(json.dumps({'state':'error','checks':[],'error':str(exc)}))\n"
            )
            return "python3 - <<'XWAV_RELEASE'\n" + code + "\nXWAV_RELEASE"
        options = {
            **request,
            "target": target,
            "operation": operation,
            "provider": provider,
            "channel": channel,
            "site": site,
            "accept_android_licenses": accept_android_licenses,
        }
        return (
            "python3 - <<'XWAV_RELEASE'\n"
            + bootstrap
            + "\ntry:\n"
            + f"    options={options!r}\n"
            + "    report=cloud['request_action'](options,SimpleNamespace(**coordinator),"
            + "SimpleNamespace(**release),_source)\n"
            + "    print(json.dumps(report))\n"
            + "except Exception as exc:\n"
            + "    print(json.dumps({'state':'error','checks':[],'artifacts':[],"
            + "'error':release['redact'](str(exc))}))\nXWAV_RELEASE"
        )
    return (
        "python3 - <<'XWAV_RELEASE'\n" + bootstrap + "\ntry:\n"
        f"    root=Path({workspace!r} or Path.cwd()).expanduser().resolve()\n"
        f"    selected=release['safe_plan'](root,{target!r},{operation!r},{provider!r},{site!r})\n"
        "    if selected['steps']: "
        f"selected['steps'][0]['accept_android_licenses']={accept_android_licenses!r}\n"
        f"    if {action!r}=='start' and not selected['ready']: "
        "raise ValueError(selected['reason'])\n"
        f"    if {action!r}=='start' and selected['android_licenses_required'] "
        f"and not {accept_android_licenses!r}: "
        "raise ValueError('Accept the Android SDK licence before automatic setup')\n"
        "    def source_version(path):\n"
        "        try: return release['fingerprint'](path)\n"
        "        except (OSError,ValueError,TypeError,KeyError): return 'unavailable'\n"
        "    report=coordinator['request_action']("
        f"{request!r},_source,'',kind='releases',discover_checks=lambda root:selected['steps'],"
        "notice=release['NOTICE'],source_fingerprint=source_version)\n"
        "    report['plans']=[release['safe_plan'](root,target,"
        f"{operation!r},{provider!r},{site!r}) "
        "for target in release['TARGETS']]\n"
        "    report['notice']=release['NOTICE']\n"
        "    release['with_live_output'](report,"
        f"coordinator['report_directory'](root,{session_id!r},'releases'))\n"
        "    print(json.dumps(report))\n"
        "except (OSError,ValueError,TypeError,KeyError) as exc:\n"
        "    print(json.dumps({'state':'error','checks':[],'artifacts':[],"
        "'error':release['redact'](str(exc))}))\n"
        "XWAV_RELEASE"
    )


def artifact_verification_command(workspace: str | None, path: str, size: int, sha256: str) -> str:
    """Hash the actual package in the owning job immediately before streaming it."""
    import re

    if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= 512 * 1024 * 1024:
        raise ValueError("Invalid package size")
    if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("Invalid package checksum")
    return (
        "python3 - <<'XWAV_VERIFY_ARTIFACT'\n"
        "import hashlib,json,os,stat\nfrom pathlib import Path\nvalid=False\ntry:\n"
        f"    root=Path({workspace!r} or Path.cwd()).expanduser().resolve()\n"
        f"    file=root/{path!r}\n"
        "    if file.resolve().is_relative_to(root) and not file.is_symlink():\n"
        "        descriptor=os.open(file,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)\n"
        "        with os.fdopen(descriptor,'rb') as stream:\n"
        "            info=os.fstat(stream.fileno())\n"
        f"            if stat.S_ISREG(info.st_mode) and info.st_size=={size}:\n"
        "                digest=hashlib.sha256()\n"
        "                for chunk in iter(lambda:stream.read(1048576),b''):\n"
        "                    digest.update(chunk)\n"
        f"                valid=digest.hexdigest()=={sha256!r}\n"
        "except OSError: pass\nprint(json.dumps({'valid':valid}))\nXWAV_VERIFY_ARTIFACT"
    )

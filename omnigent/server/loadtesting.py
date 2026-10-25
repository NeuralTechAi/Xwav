"""Reuse the persistent test coordinator for the lightweight load worker."""

from pathlib import Path

from omnigent import loadtesting_runtime, preproduction_runtime, preview_runtime


def loadtesting_command(
    session_id: str, workspace: str | None, action: str, *, max_requests: int | None = None
) -> str:
    if max_requests is not None:
        loadtesting_runtime.validate_request_count(max_requests)
    shared = Path(preproduction_runtime.__file__).read_text()
    load = Path(loadtesting_runtime.__file__).read_text()
    preview = Path(preview_runtime.__file__).read_text()
    source = (
        "import sys,json; from pathlib import Path\n"
        "coordinator={'__name__':'xwav_coordinator'}\n"
        f"exec({shared!r},coordinator)\n"
        "load={'__name__':'xwav_loadtesting'}\n"
        f"exec({load!r},load)\n"
        "if len(sys.argv)>1 and sys.argv[1]=='--worker':\n"
        "    load['worker'](Path(sys.argv[2]),sys.argv[3],"
        "coordinator['save'],coordinator['fingerprint'])\n"
    )
    request = {"session_id": session_id, "workspace": workspace, "action": action}
    return (
        "python3 - <<'XWAV_LOADTESTING'\n" + source + "\ntry:\n"
        "    print(json.dumps(coordinator['request_action']("
        f"{request!r}, {source!r}, {preview!r}, "
        f"kind='loadtesting',discover_checks=lambda root: load['discover'](root,{max_requests!r}),"
        "notice=load['NOTICE'])))\n"
        "except (OSError,ValueError,TypeError,KeyError) as exc:\n"
        "    print(json.dumps({'state':'error','checks':[],'error':str(exc)}))\n"
        "XWAV_LOADTESTING"
    )

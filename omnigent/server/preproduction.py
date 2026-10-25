"""Transport the versioned test coordinator to existing job runners."""

import json
from pathlib import Path

from omnigent import preproduction_runtime, preview_runtime


def preproduction_command(session_id: str, workspace: str | None, action: str) -> str:
    source = Path(preproduction_runtime.__file__).read_text()
    preview_source = Path(preview_runtime.__file__).read_text()
    request = json.dumps({"session_id": session_id, "workspace": workspace, "action": action})
    invocation = f"request_action(json.loads({request!r}), {source!r}, {preview_source!r})"
    return (
        "python3 - <<'XWAV_PREPRODUCTION'\n"
        + source
        + "\ntry:\n    print(json.dumps("
        + invocation
        + "))\n"
        + "except (OSError, ValueError, TypeError, KeyError) as exc:\n"
        + "    print(json.dumps({'state': 'error', 'checks': [], 'error': str(exc)}))\n"
        + "XWAV_PREPRODUCTION"
    )

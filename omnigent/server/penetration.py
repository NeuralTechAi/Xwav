"""Transport a read-only Strix report reader to existing job runtimes."""

import json
from pathlib import Path

from omnigent import penetration_runtime


def penetration_command(workspace: str | None, run_id: str | None = None) -> str:
    source = Path(penetration_runtime.__file__).read_text()
    parameters = json.dumps({"workspace": workspace, "run_id": run_id})
    return (
        "python3 - <<'XWAV_STRIX_REPORT'\n"
        + source
        + "\ntry:\n    print(json.dumps(inspect_reports(**json.loads("
        + repr(parameters)
        + "))))\n"
        + "except (OSError, ValueError, TypeError, KeyError):\n"
        + "    print(json.dumps({'state':'error','runs':[],'findings':[],"
        + "'error':'Could not read Strix reports. Check for invalid JSON, "
        + "oversized artifacts or symbolic links.'}))\n"
        + "XWAV_STRIX_REPORT"
    )

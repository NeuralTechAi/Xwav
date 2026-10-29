"""On-demand dashboard evidence for all job harnesses."""

import asyncio
import json
import re
from pathlib import Path

from omnigent import diagnostics_runtime, penetration_runtime, preproduction_runtime


def requested_kinds(content: list) -> list[str]:
    text = "\n".join(block.get("text", "") for block in content if isinstance(block, dict))[:16000]
    patterns = {
        "preproduction": r"pre[\s-]*production|quality lab",
        "loadtesting": r"load[\s-]*test|stress[\s-]*test|soak[\s-]*test|performance lab",
        "penetration": r"penetration|pentest|strix|security lab",
        "releases": r"\bcompil\w*|\bbuild\w*|\bdeploy\w*|installable|release studio",
    }
    kinds = [kind for kind, pattern in patterns.items() if re.search(pattern, text, re.I)]
    inspecting_issue = re.search(
        r"check|inspect|fix|error|fail|issue|repair|diagnos|debug|dashboard|broken", text, re.I
    )
    if "releases" in kinds and not inspecting_issue:
        kinds.remove("releases")
    if not kinds and inspecting_issue and re.search(r"dashboard", text, re.I):
        return list(diagnostics_runtime.KINDS)
    return kinds


def requested_run(content: list, kinds: list[str]) -> str | None:
    if "penetration" not in kinds:
        return None
    text = "\n".join(block.get("text", "") for block in content if isinstance(block, dict))
    match = re.search(r"\(run ([a-f0-9]{32})\)", text[:16000])
    return match.group(1) if match else None


def diagnostics_command(
    session_id: str, workspace: str | None, kinds: list[str], run_id: str | None = None
) -> str:
    if not kinds or any(kind not in diagnostics_runtime.KINDS for kind in kinds):
        raise ValueError("Choose a supported dashboard")
    if run_id is not None and not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise ValueError("Invalid scan run identifier")
    sources = [
        Path(module.__file__).read_text()
        for module in (
            preproduction_runtime,
            penetration_runtime,
            diagnostics_runtime,
        )
    ]
    code = "import json\n"
    for name, source in zip(("coordinator", "penetration", "diagnostics"), sources, strict=True):
        code += f"{name}={{'__name__':'xwav_evidence'}}\nexec({source!r},{name})\n"
    code += (
        f"print(json.dumps(diagnostics['collect']({session_id!r},{workspace!r},{kinds!r},"
        "coordinator['report_directory'],penetration['inspect_reports'],"
        f"coordinator['fingerprint'],{run_id!r})))\n"
    )
    return "python3 - <<'XWAV_DIAGNOSTICS'\n" + code + "XWAV_DIAGNOSTICS"


async def collect_diagnostics(
    runner, session_id: str, workspace: str | None, kinds: list[str], run_id: str | None = None
) -> dict:
    response = await runner.post(
        f"/v1/sessions/{session_id}/resources/environments/default/shell",
        json={"command": diagnostics_command(session_id, workspace, kinds, run_id), "timeout": 12},
        timeout=15,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("exit_code") != 0:
        raise ValueError("Evidence reader failed")
    payload = json.loads(result["stdout"].strip().splitlines()[-1])
    if payload.get("session_id") != session_id or not isinstance(payload.get("reports"), list):
        raise ValueError("Invalid dashboard evidence")
    if "penetration" in kinds:
        from omnigent.server.strix_jobs import report as managed_report

        managed = (
            await asyncio.to_thread(managed_report, session_id, run_id)
            if run_id
            else await asyncio.to_thread(managed_report, session_id)
        )
        if managed is not None:
            payload["reports"] = [r for r in payload["reports"] if r["kind"] != "penetration"]
            payload["reports"].append(diagnostics_runtime.summarize("penetration", managed))
    return json.loads(diagnostics_runtime.redact_evidence(json.dumps(payload)))


def evidence_text(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, indent=2)
    if len(raw) > 30000:
        raw = raw[:30000] + "\n[Evidence truncated; inspect the report_path for full details.]"
    return (
        diagnostics_runtime.GUIDANCE
        + "\n\n<Xwav-dashboard-evidence>\n"
        + raw
        + "\n</Xwav-dashboard-evidence>"
    )

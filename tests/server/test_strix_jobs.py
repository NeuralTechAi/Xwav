"""Automatic scans snapshot the whole project and launch a bounded, reusable worker."""

import asyncio
import io
import json
import zipfile

import pytest
from fastapi import HTTPException

from omnigent.server import strix_jobs
from tests._helpers.polling import poll_until_async
from tests.billing.test_subscriptions import service as service


@pytest.fixture
def scan_setup(service, tmp_path, monkeypatch):
    service.config.providers[0].models[0].input_usd_per_million = 0
    service.config.providers[0].models[0].output_usd_per_million = 0
    root = tmp_path / "service"
    monkeypatch.setenv("XWAV_STRIX_RUNTIME_ROOT", str(root))
    executable = tmp_path / "fixture-strix"
    executable.write_text("""#!/usr/bin/env python3
import json,sys,time,os
from pathlib import Path
args=sys.argv
assert os.environ['LLM_PREFLIGHT_TIMEOUT']=='150'
assert args[args.index('--scope-mode')+1]=='full'
source=Path(args[args.index('--target')+1])
assert (source/'unchanged.py').is_file() and (source/'nested/new.py').is_file()
(source/'unchanged.py').write_text('scanner edits only disposable copy')
run=Path.cwd()/'strix_runs/fixture'
run.mkdir(parents=True)
(run/'run.json').write_text(json.dumps({'status':'running'}))
time.sleep(1)
findings=[{'id':'finding-1','title':'Fixture evidence','severity':'high'}]
(run/'vulnerabilities.json').write_text(json.dumps(findings))
(run/'run.json').write_text(json.dumps({'status':'completed'}))
""")
    executable.chmod(0o755)
    monkeypatch.setenv("XWAV_STRIX_EXECUTABLE", str(executable))

    async def snapshot():
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("unchanged.py", "original")
            archive.writestr("nested/new.py", "new file")
            archive.writestr(".omnigent/private", "never given to scanner")
        output.seek(0)
        return output

    return service, snapshot, root


@pytest.mark.asyncio
async def test_start_reuses_running_job_then_fresh_run_and_retains_results(scan_setup):
    service, snapshot, _ = scan_setup
    first = await strix_jobs.action("project-job", "alice", "start", service, snapshot)
    second = await strix_jobs.action("project-job", "alice", "start", service, snapshot)
    assert first["state"] == "running" and first["run"]["id"] == second["run"]["id"]

    def finished():
        result = strix_jobs.report("project-job")
        return result if result and result["state"] != "running" else None

    await poll_until_async(finished, timeout_s=45, interval_s=0.2)
    complete = strix_jobs.report("project-job")
    assert complete["state"] == "complete", complete
    assert complete["counts"]["high"] == 1
    assert not (
        strix_jobs.session_directory("project-job") / first["run"]["id"] / "source"
    ).exists()
    fresh = await strix_jobs.action("project-job", "alice", "start", service, snapshot)
    assert fresh["run"]["id"] != first["run"]["id"]
    await poll_until_async(finished, timeout_s=45, interval_s=0.2)
    assert len(strix_jobs.report("project-job")["runs"]) == 2
    assert strix_jobs.report("other-job") is None


@pytest.mark.asyncio
async def test_scan_tokens_are_free_only_revocable_and_do_not_replace_user_token(
    scan_setup, monkeypatch
):
    service, snapshot, _ = scan_setup
    user_token = service.store.rotate_token("alice")

    async def slow_snapshot():
        await asyncio.sleep(1)
        return await snapshot()

    result = await strix_jobs.action("tokens-job", "alice", "start", service, slow_snapshot)
    directory = strix_jobs.session_directory("tokens-job") / result["run"]["id"]
    token = json.loads((directory / "private.json").read_text())["token"]
    assert strix_jobs.scan_identity(service, token, "free") == "alice"
    with pytest.raises(HTTPException):
        strix_jobs.scan_identity(service, token, "managed")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from omnigent.server.routes.billing import create_billing_router

    async def exhausted(*args, **kwargs):
        raise HTTPException(503, "All configured free models are temporarily unavailable.")

    monkeypatch.setattr(service, "infer", exhausted)
    app = FastAPI()
    app.include_router(create_billing_router(service), prefix="/v1")
    with TestClient(app) as client:
        for credential, status in [(token, 424), (user_token, 503)]:
            response = client.post(
                "/v1/inference/free/chat/completions",
                json={"model": "test/small"},
                headers={"Authorization": "Bearer " + credential},
            )
            assert response.status_code == status
            if status == 424:
                assert response.headers["x-should-retry"] == "false"
    await strix_jobs.action("tokens-job", "alice", "cancel", service, snapshot)
    with pytest.raises(HTTPException):
        strix_jobs.scan_identity(service, token, "free")
    assert service.store.token_owner(user_token) == "alice"
    await poll_until_async(
        lambda: strix_jobs.report("tokens-job")["state"] == "stopped", timeout_s=10
    )


def test_snapshot_refuses_traversal_and_symlinks(tmp_path):
    for name, mode in [("../escape", 0), ("link", 0o120777 << 16)]:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            entry = zipfile.ZipInfo(name)
            entry.external_attr = mode
            archive.writestr(entry, "outside")
        output.seek(0)
        with pytest.raises(ValueError):
            strix_jobs.extract_snapshot(output, tmp_path / "source")
    assert not (tmp_path / "escape").exists()


@pytest.mark.asyncio
async def test_engine_failure_can_be_retried_without_reusing_failed_run(
    scan_setup, monkeypatch, tmp_path
):
    service, snapshot, _ = scan_setup
    executable = tmp_path / "broken-strix"
    executable.write_text("#!/usr/bin/env python3\nraise SystemExit(1)\n")
    executable.chmod(0o755)
    monkeypatch.setenv("XWAV_STRIX_EXECUTABLE", str(executable))
    first = await strix_jobs.action("failed-job", "alice", "start", service, snapshot)
    await poll_until_async(
        lambda: strix_jobs.report("failed-job")["state"] == "error", timeout_s=30
    )
    failed = strix_jobs.report("failed-job")
    assert "stopped before completing" in failed["error"]
    assert not (
        strix_jobs.session_directory("failed-job") / first["run"]["id"] / "source"
    ).exists()
    retry = await strix_jobs.action("failed-job", "alice", "start", service, snapshot)
    assert retry["run"]["id"] != first["run"]["id"]
    await poll_until_async(
        lambda: strix_jobs.report("failed-job")["state"] == "error", timeout_s=30
    )


@pytest.mark.asyncio
async def test_cancel_stops_running_engine_and_removes_source(scan_setup, monkeypatch, tmp_path):
    service, snapshot, _ = scan_setup
    executable = tmp_path / "slow-strix"
    executable.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(60)\n")
    executable.chmod(0o755)
    monkeypatch.setenv("XWAV_STRIX_EXECUTABLE", str(executable))
    first = await strix_jobs.action("cancel-job", "alice", "start", service, snapshot)
    await poll_until_async(
        lambda: (
            strix_jobs.report("cancel-job").get("phase")
            == "Scanning the entire project with Strix"
        ),
        timeout_s=30,
    )
    await strix_jobs.action("cancel-job", "alice", "cancel", service, snapshot)
    await poll_until_async(
        lambda: strix_jobs.report("cancel-job")["state"] == "stopped", timeout_s=30
    )
    assert not (
        strix_jobs.session_directory("cancel-job") / first["run"]["id"] / "source"
    ).exists()


def test_failure_diagnostics_redact_logs_and_repair_old_generic_status(tmp_path, monkeypatch):
    monkeypatch.setenv("XWAV_STRIX_RUNTIME_ROOT", str(tmp_path))
    run_id = "a" * 32
    directory = strix_jobs.session_directory("failed-report") / run_id
    strix_jobs.save(
        directory / "state.json",
        {
            "state": "error",
            "phase": "Scanning the entire project with Strix",
            "error": "Strix could not complete. Check Docker availability",
        },
    )
    (directory.parent / "latest").write_text(run_id)
    (directory / "engine.log").write_text(
        "private token abc123\nModel provider rejected the request (400)"
    )
    report = strix_jobs.report("failed-report")
    assert "HTTP 400" in report["error"] and report["phase"] == "Scan failed"
    assert "abc123" not in report["error"]
    (directory / "engine.log").write_text(
        "All configured free models are temporarily unavailable. secret"
    )
    assert "no capacity" in strix_jobs.failure_detail(directory)
    assert "secret" not in strix_jobs.failure_detail(directory)

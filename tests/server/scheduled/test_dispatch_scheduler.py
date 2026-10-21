"""Database scheduler contracts against the real store, without hosts or sandboxes."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest

from omnigent.db.db_models import current_workspace_id, workspace_scope
from omnigent.server.scheduled.dispatch_scheduler import (
    PersistentTaskScheduler,
    StartupLease,
    StartupLeaseLost,
)
from omnigent.server.scheduled.schedule import occurrence_host_id
from omnigent.stores.scheduled_task_store.sqlalchemy_store import SqlAlchemyScheduledTaskStore
from tests.server.scheduled.test_scheduler import FakeClock


@pytest.fixture
def store(db_uri: str) -> SqlAlchemyScheduledTaskStore:
    store = SqlAlchemyScheduledTaskStore(db_uri)
    store.configure_dispatch(True)
    return store


def _task(store: SqlAlchemyScheduledTaskStore, seed: str = "task", **kwargs):
    task = store.create(
        uuid.uuid5(uuid.NAMESPACE_DNS, seed).hex,
        seed,
        "prompt",
        "FREQ=HOURLY",
        None,
        uuid.uuid4().hex,
        "UTC",
        **kwargs,
    )
    return store.get(task.id)


async def _drain(scheduler: PersistentTaskScheduler) -> None:
    if scheduler._recovery is not None:
        await scheduler._recovery
    await asyncio.gather(*list(scheduler._startups.values()))


async def test_enabling_dispatch_does_not_replay_legacy_timer_occurrences(store, monkeypatch):
    from omnigent.stores.scheduled_task_store import sqlalchemy_store

    store.configure_dispatch(False)
    task = _task(store)
    assert task.next_run_at is None
    clock = FakeClock(task.created_at + 30 * 86400)
    monkeypatch.setattr(sqlalchemy_store, "now_epoch", lambda: int(clock.now()))
    store.update(task.id, rrule="FREQ=DAILY;BYHOUR=9")
    store.update(task.id, last_run_at=int(clock.now()))
    assert store.get(task.id).next_run_at is None
    fire = AsyncMock()
    scheduler = PersistentTaskScheduler(store, fire, AsyncMock(), now=clock.now)
    await scheduler.poll_once()
    await _drain(scheduler)
    fire.assert_not_awaited()
    assert store.get(task.id).next_run_at > clock.now()
    assert _task(store, "created_after_enabling").next_run_at is not None


async def test_bootstrap_retries_after_concurrent_metadata_edit(store, monkeypatch):
    store.configure_dispatch(False)
    task = _task(store)
    original = store.initialize_next_run_at
    attempts = 0

    def initialize(snapshot, next_run_at):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            store.update(task.id, prompt="edited during bootstrap")
        return original(snapshot, next_run_at)

    monkeypatch.setattr(store, "initialize_next_run_at", initialize)
    scheduler = PersistentTaskScheduler(store, AsyncMock(), AsyncMock())
    await scheduler.poll_once()
    await _drain(scheduler)
    assert store.get(task.id).next_run_at is None
    await scheduler.poll_once()
    await _drain(scheduler)
    assert store.get(task.id).next_run_at is not None
    assert store.get(task.id).prompt == "edited during bootstrap"
    assert attempts == 2


async def test_unfinished_fire_return_warns_and_leaves_run_for_recovery(store, caplog):
    task = _task(store)
    clock = FakeClock(task.next_run_at)
    recover = AsyncMock(return_value="failed")
    scheduler = PersistentTaskScheduler(store, AsyncMock(), recover, now=clock.now)
    await scheduler.poll_once()
    await _drain(scheduler)
    run = store.list_runs(task.id)[0][0]
    assert run.status == "starting"
    assert "without finishing startup" in caplog.text
    clock.advance(120)
    await scheduler.poll_once()
    await _drain(scheduler)
    recover.assert_awaited_once_with(run)
    assert store.list_runs(task.id)[0][0].status == "failed"


async def test_two_pollers_fire_once_and_do_not_catch_up_outage(store) -> None:
    with workspace_scope(42):
        task = _task(store)
    clock = FakeClock(task.next_run_at + 7200)
    fired = []

    async def fire(snapshot, lease):
        assert current_workspace_id() == 42
        assert snapshot == task
        fired.append(lease.run)
        session_id = uuid.uuid4().hex
        await lease.attach_session(session_id)
        assert store.list_runs(task.id)[0][0].conversation_id == session_id
        assert lease.run.status == "starting"
        await lease.finish("running")

    schedulers = [
        PersistentTaskScheduler(store, fire, AsyncMock(), now=clock.now) for _ in range(2)
    ]
    await asyncio.gather(*(scheduler.poll_once() for scheduler in schedulers))
    await asyncio.gather(*(_drain(scheduler) for scheduler in schedulers))
    assert len(fired) == 1
    assert fired[0].scheduled_at == task.next_run_at
    with workspace_scope(42):
        assert store.get(task.id).next_run_at > clock.now()
        assert len(store.list_runs(task.id)[0]) == 1
    await schedulers[0].poll_once()
    await _drain(schedulers[0])
    assert len(fired) == 1


async def test_scan_pages_past_unowned_tasks_and_ownership_errors(store) -> None:
    tasks = [_task(store, str(i), host_id=uuid.uuid4().hex) for i in range(3)]
    clock = FakeClock(max(task.next_run_at for task in tasks))
    ordered = store.list_due_tasks(int(clock.now()))
    own = ordered[-1]
    calls = []

    async def owns(workspace, host):
        calls.append(host)
        if host == ordered[0].host_id:
            raise RuntimeError("no assignment")
        return host == own.host_id

    async def fire(task, lease):
        assert lease.run.host_id == own.host_id
        await lease.finish("running")

    scheduler = PersistentTaskScheduler(
        store, fire, AsyncMock(), owns_host=owns, now=clock.now, batch_size=1
    )
    await scheduler.poll_once()
    await _drain(scheduler)
    assert calls == [task.host_id for task in ordered]
    assert store.list_runs(own.id)[0][0].status == "running"
    assert store.list_runs(ordered[0].id)[0] == []


async def test_startup_limit_leaves_unclaimed_work_for_next_poll(store) -> None:
    tasks = [_task(store, str(i)) for i in range(2)]
    clock = FakeClock(max(task.next_run_at for task in tasks))
    started = asyncio.Event()
    release = asyncio.Event()

    async def fire(task, lease):
        started.set()
        await release.wait()
        await lease.finish("running")

    scheduler = PersistentTaskScheduler(store, fire, AsyncMock(), now=clock.now, max_startups=1)
    await scheduler.poll_once()
    await asyncio.wait_for(started.wait(), 10)
    assert len(store.list_due_tasks(int(clock.now()))) == 1
    release.set()
    await _drain(scheduler)
    await scheduler.poll_once()
    await _drain(scheduler)
    assert store.list_due_tasks(int(clock.now())) == []


async def test_heartbeat_renews_only_local_startup_and_stops_after_prompt(
    store, monkeypatch
) -> None:
    task = _task(store)
    clock = FakeClock(task.next_run_at)
    started = asyncio.Event()
    renewed = asyncio.Event()
    release = asyncio.Event()
    leases = []
    original_renew = store.renew_starting_run
    loop = asyncio.get_running_loop()

    def renew(run_id, *, now, lease_seconds):
        result = original_renew(run_id, now=now, lease_seconds=lease_seconds)
        if now() == task.next_run_at + 30:
            loop.call_soon_threadsafe(renewed.set)
        return result

    monkeypatch.setattr(store, "renew_starting_run", renew)

    async def fire(task, lease):
        leases.append(lease)
        started.set()
        await release.wait()
        await lease.finish("running")

    scheduler = PersistentTaskScheduler(
        store, fire, AsyncMock(), now=clock.now, renewal_seconds=0.01
    )
    try:
        await scheduler.poll_once()
        await asyncio.wait_for(started.wait(), 10)
        clock.advance(30)
        await asyncio.wait_for(renewed.wait(), 10)
        assert store.list_runs(task.id)[0][0].lease_expires_at == task.next_run_at + 150
        release.set()
        await _drain(scheduler)
        assert leases[0].run.status == "running"
        assert store.list_runs(task.id)[0][0].lease_expires_at is None
        clock.advance(200)
        await scheduler.poll_once()
        assert store.list_runs(task.id)[0][0].status == "running"
    finally:
        await scheduler.stop()


async def test_expiry_cancels_old_executor_and_reconciles_without_refiring(store) -> None:
    task = _task(store)
    clock = FakeClock(task.next_run_at)
    started = asyncio.Event()
    cancelled = asyncio.Event()
    fire_calls = 0

    async def fire(task, lease):
        nonlocal fire_calls
        fire_calls += 1
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    reconciled = []

    async def recover(run):
        # This fake executor has not sent a prompt or created a sandbox.
        reconciled.append(run)
        return "failed"

    scheduler = PersistentTaskScheduler(store, fire, recover, now=clock.now)
    try:
        await scheduler.poll_once()
        await asyncio.wait_for(started.wait(), 10)
        clock.advance(120)
        await scheduler.poll_once()
        await _drain(scheduler)
        assert cancelled.is_set()
        assert reconciled[0].status == "starting"
        assert store.list_runs(task.id)[0][0].status == "failed"
        assert fire_calls == 1
    finally:
        await scheduler.stop()


async def test_new_owner_does_not_renew_other_process_claim(store) -> None:
    task = _task(store, execution_target="managed_sandbox")
    clock = FakeClock(task.next_run_at)
    host = occurrence_host_id(task, f"schedule:{task.next_run_at}")
    run = store.claim_scheduled_run(
        task,
        now=int(clock.now()),
        next_run_at=task.next_run_at + 3600,
        host_id=host,
        lease_seconds=120,
    )
    recovered = AsyncMock(return_value="failed")
    fire = AsyncMock()
    scheduler = PersistentTaskScheduler(store, fire, recovered, now=clock.now)
    clock.advance(30)
    await scheduler.poll_once()
    await _drain(scheduler)
    assert store.list_runs(task.id)[0][0].lease_expires_at == run.lease_expires_at
    recovered.assert_not_awaited()
    clock.advance(90)
    await scheduler.poll_once()
    await _drain(scheduler)
    recovered.assert_awaited_once_with(run)
    fire.assert_not_awaited()


async def test_lease_checkpoint_cannot_revive_expired_claim(store) -> None:
    task = _task(store)
    clock = FakeClock(task.next_run_at)
    run = store.claim_scheduled_run(
        task,
        now=int(clock.now()),
        next_run_at=task.next_run_at + 3600,
        host_id=None,
        lease_seconds=120,
    )
    lease = StartupLease(store, run, now=clock.now, lease_seconds=120)
    clock.advance(120)
    with pytest.raises(StartupLeaseLost):
        await lease.check()
    with pytest.raises(StartupLeaseLost):
        await lease.finish("running")
    assert store.list_runs(task.id)[0][0] == run


async def test_loop_retries_after_boot_database_outage_and_stops(store, monkeypatch) -> None:
    original = store.list_active_all_workspaces
    attempts = 0
    recovered = asyncio.Event()
    loop = asyncio.get_running_loop()

    def read():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary outage")
        result = original()
        loop.call_soon_threadsafe(recovered.set)
        return result

    monkeypatch.setattr(store, "list_active_all_workspaces", read)
    scheduler = PersistentTaskScheduler(store, AsyncMock(), AsyncMock(), poll_seconds=0.01)
    await scheduler.start()
    await scheduler.start()
    try:
        await asyncio.wait_for(recovered.wait(), 10)
        assert attempts == 2
        assert scheduler.is_started
    finally:
        await scheduler.stop()
    assert not scheduler.is_started


@pytest.mark.parametrize("failure", ["exception", "timeout"])
@pytest.mark.parametrize("deleted", [False, True])
async def test_expired_cleanup_failure_is_retried_without_another_fire(
    store, failure, deleted
) -> None:
    task = _task(store, execution_target="managed_sandbox")
    clock = FakeClock(task.next_run_at)
    run = store.claim_scheduled_run(
        task,
        now=int(clock.now()),
        next_run_at=task.next_run_at + 3600,
        host_id=occurrence_host_id(task, f"schedule:{task.next_run_at}"),
        lease_seconds=120,
    )
    if deleted:
        assert store.delete(task.id)
    clock.advance(120)

    async def recovery(run):
        assert store.get(task.id) is not None
        assert run.host_id == occurrence_host_id(task, f"schedule:{task.next_run_at}")
        if recover.await_count == 1:
            if failure == "timeout":
                await asyncio.Event().wait()
            raise RuntimeError("cleanup unavailable")
        return "failed"

    recover = AsyncMock(side_effect=recovery)
    fire = AsyncMock()
    scheduler = PersistentTaskScheduler(store, fire, recover, now=clock.now, recovery_seconds=0.05)
    await scheduler.poll_once()
    await _drain(scheduler)
    assert store.list_runs(task.id)[0] == [run]
    await scheduler.poll_once()
    await _drain(scheduler)
    if deleted:
        assert store.get(task.id) is None
        assert store.list_runs(task.id)[0] == []
    else:
        assert store.list_runs(task.id)[0][0].status == "failed"
    assert recover.await_count == 2
    fire.assert_not_awaited()


def test_d1_dispatch_is_rejected_before_polling(store, monkeypatch) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(
        store, "_engine", SimpleNamespace(dialect=SimpleNamespace(name="cloudflare_d1"))
    )
    with pytest.raises(NotImplementedError, match="multi-statement transactions"):
        PersistentTaskScheduler(store, AsyncMock(), AsyncMock())


@pytest.mark.parametrize("bootstrap", [False, True])
async def test_subminimum_legacy_schedule_is_paused(store, bootstrap, caplog) -> None:
    from sqlalchemy import update

    from omnigent.db.db_models import SqlScheduledTask

    task = _task(store)
    invalid = store.update(task.id, rrule="FREQ=MINUTELY")
    clock = FakeClock(invalid.next_run_at)
    if bootstrap:
        with store._session_immediate("test_legacy_schedule") as session:
            session.execute(
                update(SqlScheduledTask)
                .where(SqlScheduledTask.id == task.id)
                .values(next_run_at=None)
            )
    fire = AsyncMock()
    scheduler = PersistentTaskScheduler(store, fire, AsyncMock(return_value=None), now=clock.now)
    await scheduler.poll_once()
    await _drain(scheduler)
    await scheduler.poll_once()
    await _drain(scheduler)
    fire.assert_not_awaited()
    assert store.list_runs(task.id)[0] == []
    assert store.get(task.id).state == "paused"
    assert store.get(task.id).next_run_at is None
    assert caplog.text.count("invalid schedule") == 1


@pytest.mark.parametrize("action", ["check", "attach_session", "finish"])
async def test_lease_expiring_while_waiting_for_row_lock_is_not_revived(
    store, monkeypatch, action
) -> None:
    from sqlalchemy.orm import Session

    from omnigent.db.db_models import SqlScheduledTaskRun

    task = _task(store)
    clock = FakeClock(task.next_run_at)
    run = store.claim_scheduled_run(
        task,
        now=int(clock.now()),
        next_run_at=task.next_run_at + 3600,
        host_id=None,
        lease_seconds=120,
    )
    lease = StartupLease(store, run, now=clock.now, lease_seconds=120)
    clock.advance(119)
    original_get = Session.get

    def delayed_get(session, entity, *args, **kwargs):
        row = original_get(session, entity, *args, **kwargs)
        if entity is SqlScheduledTaskRun and kwargs.get("with_for_update"):
            clock.advance(2)
        return row

    monkeypatch.setattr(Session, "get", delayed_get)
    with pytest.raises(StartupLeaseLost):
        if action == "check":
            await lease.check()
        elif action == "attach_session":
            await lease.attach_session(uuid.uuid4().hex)
        else:
            await lease.finish("running")
    assert store.list_runs(task.id)[0] == [run]


async def test_slow_recovery_does_not_block_due_tasks_and_is_drained_on_stop(store) -> None:
    expired_task = _task(store, "expired")
    due_task = _task(store, "due")
    clock = FakeClock(max(expired_task.next_run_at, due_task.next_run_at))
    expired_run = store.claim_scheduled_run(
        expired_task,
        now=int(clock.now()),
        next_run_at=int(clock.now()) + 3600,
        host_id=None,
        lease_seconds=120,
    )
    clock.advance(120)
    recovering = asyncio.Event()
    cancelled = asyncio.Event()

    async def recover(run):
        recovering.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    async def fire(task, lease):
        assert task.id == due_task.id
        await lease.finish("running")

    recovery = AsyncMock(side_effect=recover)
    scheduler = PersistentTaskScheduler(
        store,
        fire,
        recovery,
        now=clock.now,
        recovery_seconds=60,
    )
    try:
        await scheduler.poll_once()
        await asyncio.wait_for(recovering.wait(), 10)
        await asyncio.gather(*list(scheduler._startups.values()))
        assert store.list_runs(due_task.id)[0][0].status == "running"
        await scheduler.poll_once()
        recovery.assert_awaited_once_with(expired_run)
        assert not cancelled.is_set()
    finally:
        await scheduler.stop()
    assert cancelled.is_set()
    assert store.list_runs(expired_task.id)[0] == [expired_run]


@pytest.mark.parametrize("bootstrap", [False, True])
async def test_schedule_search_failure_preserves_cursor_and_retries(
    store, monkeypatch, bootstrap
) -> None:
    from sqlalchemy import update

    from omnigent.db.db_models import SqlScheduledTask
    from omnigent.server.scheduled import schedule
    from omnigent.server.scheduled.rrule import RRuleSearchError

    task = _task(store)
    healthy = _task(store, "healthy")
    clock = FakeClock(task.next_run_at)
    if bootstrap:
        with store._session_immediate("test_legacy_schedule") as session:
            session.execute(
                update(SqlScheduledTask)
                .where(SqlScheduledTask.id == task.id)
                .values(next_run_at=None)
            )
    snapshot = store.get(task.id)
    original = schedule.get_next_fire_time
    failing = True

    def calculate(rule, after, tz, *, anchor=None):
        # Distinguish the task without replacing schedule error handling.
        if failing and rule == "FREQ=HOURLY":
            raise RRuleSearchError("RRULE search exceeds the supported time limit")
        return original(rule, after, tz, anchor=anchor)

    store.update(healthy.id, rrule="FREQ=HOURLY;INTERVAL=1")
    monkeypatch.setattr(schedule, "get_next_fire_time", calculate)

    async def fire(task, lease):
        await lease.finish("running")

    scheduler = PersistentTaskScheduler(store, fire, AsyncMock(), now=clock.now)
    try:
        await scheduler.poll_once()
        await _drain(scheduler)
        assert store.get(task.id) == snapshot
        assert store.list_runs(task.id)[0] == []
        assert store.list_runs(healthy.id)[0][0].status == "running"
        failing = False
        await scheduler.poll_once()
        await _drain(scheduler)
        assert store.get(task.id).next_run_at > clock.now()
        if bootstrap:
            clock.advance(3600)
            await scheduler.poll_once()
            await _drain(scheduler)
        assert store.list_runs(task.id)[0][0].status == "running"
    finally:
        await scheduler.stop()

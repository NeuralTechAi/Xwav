# Database scheduler integration

`PersistentTaskScheduler` implements the scheduler work item. It uses the
dispatch fields on `scheduled_tasks` and `scheduled_task_runs`. The shared backend/UI
release flag `automations_v2` defaults off, keeping the existing timers even
when callbacks are supplied. The same flag is exposed through /v1/info for the
automation UI improvements to use. To select DB dispatch, set
`OMNIGENT_FEATURES=automations_v2` and supply
`create_app(..., scheduled_task_dispatch=ScheduledTaskDispatchHooks(...))`.
Enabling the flag without a compatible store and the callbacks fails startup;
it never silently falls back to timers.
The standalone entrypoint does not supply these callbacks yet. The shared flag
cannot be enabled there, including for the UI, until the fire-path work is wired.

This flag is resolved once at startup. The switch applies to the whole server;
do not mix timer and DB scheduler replicas for the same database, since timer
fires do not participate in claims. Per-workspace automation gating is
separate from this deployment-wide scheduler selection.

## Contract with the fire path

Supply these callbacks through `ScheduledTaskDispatchHooks`:

- `on_fire(task, lease)` awaits the entire startup using the task snapshot and
  `lease.run`. It must update that run, not insert another history row. Call
  `await lease.check()` before advancing external startup actions. After creating
  a session, call `await lease.attach_session(session_id)` before sending the
  prompt, so recovery can find the session. Call `await lease.finish("running")`
  after sending the prompt, or `finish("failed", error=..., error_code=...)`
  after a known startup failure and successful cleanup. If cleanup is unresolved,
  leave the claim for recovery. Do not detach startup work into background tasks
  or swallow cancellation. A cancellation cannot undo an already accepted RPC.
- `on_expired(run)` inspects the linked session and target. Return `"running"`
  if the prompt was sent. If it was not sent, clean up the unfinished sandbox
  idempotently, then return `"failed"`. The scheduler conditionally records that
  result. Return `None` or raise if the outcome/cleanup is unresolved; the same
  startup remains eligible on a later sweep. Never resend the prompt here.
  Respect cancellation and keep cleanup in the callback so timeout/shutdown
  cannot leave detached cleanup running.
  Different replicas can call this concurrently for the same expired run.
  Inspection and cleanup must be safe under concurrent calls, including a sandbox
  already removed by another callback. The conditional database transition only
  protects run status; it does not serialize external cleanup.
- `owns_host(workspace_id, host_id)` decides which occurrences and expired runs
  this replica handles. It defaults to true. Deployments with host ownership
  routing must return false without an assignment and for unsupported hostless
  targets; errors skip the row.

The fire-path refactor, manual Run now claiming, owner delegation and Arclet
launch/cleanup are separate work items. The existing fire callback cannot be
passed directly: it creates a run at the end and returns before startup finishes.
Before enabling the flag, the fire-path integration must also handle completion
arriving while a run is still starting, and recovery finding an already-terminal
session. The current recovery result only distinguishes running from failed.

## Scheduling and leases

Defaults are 30-second polls, 30-second renewal intervals, a 120-second startup
lease, a 30-second timeout per recovery attempt, and at most 100 simultaneous
local startups. Constructor parameters make
these configurable. Polls do not overlap. Heartbeats run independently of polling
and only renew this process's active startups. Shutdown cancels local work and
lets unresolved claims expire; a new owner does not renew them automatically.
Renewals and startup transitions read the clock after acquiring the run lock,
including on transaction retries.

A separate, non-overlapping sweep reconciles expired startups. Slow cleanup
does not block due-task polling. Timeout or failure leaves the startup eligible
for another sweep; shutdown cancels and drains both startup and recovery work.

The app configures store cursor maintenance from the same `automations_v2` flag;
direct scheduler construction enables it too. With the flag off, creates leave
`next_run_at` NULL and schedule edits do not calculate it. With it on, creates and
schedule/timezone/state edits maintain the cursor. Run metadata and prompt-only
updates do not calculate or move it. Bootstrap initializes active legacy rows with
NULL cursors to a future occurrence, retrying if a concurrent edit wins. Existing
non-NULL cursors survive restarts for outage catch-up. Permanently invalid rules
are paused conditionally on the unchanged task; search-budget failures are retried.
Discovery then keyset-pages the due-task and expired-lease indexes,
including past rows assigned to other replicas. One transaction locks and rechecks
the complete task snapshot, inserts its unique starting run, and moves the cursor
past now. Missed intervals do not cause a burst of catch-up fires; one oldest due
occurrence is dispatched and the next occurrence is in the future. Automatic
retry and missed-occurrence history are deferred.
If an edit revisits an occurrence already in run history, the scheduler advances
the cursor without inserting or firing another run.

Deleting a task retains unfinished claimed runs and a deleted task row, including
the metadata needed for recovery. The API hides it and the scheduler cannot claim
new occurrences. Existing claims may finish; expired claims remain discoverable
until cleanup succeeds. Each terminal transition removes its retained run, and
the last one removes the deleted task. Legacy runs without a trigger key retain
the existing immediate-deletion behavior.

Persisted schedules use the task creation day's local midnight as a stable RRULE
anchor, including for COUNT and INTERVAL rules. Pausing/resuming and editing a
schedule do not reset that anchor. The legacy timer scheduler retains its existing
calculation. This keeps persisted COUNT exhaustion stable across restarts.
Unbounded recurrences skip historical periods while preserving their original
interval phase; their search horizon is relative to the query time. COUNT rules
retain their full occurrence count. Work/time-limit errors preserve the stored
cursor for retry, including during bootstrap; they never mean schedule exhaustion.

The SQL implementation uses row locks on PostgreSQL/MySQL/CockroachDB and
`BEGIN IMMEDIATE` on SQLite. Cloudflare D1's current REST driver cannot provide
this multi-statement transaction; the new scheduler rejects it before starting.

## Rollout and verification

Deploy the schema and `starting` status readers before enabling database dispatch.
Wire and verify the claimed-run callbacks first, then switch all scheduler replicas
together. Keep the flag off until the callbacks and any required ownership hook are
ready. To roll back, first stop new task admission and let claimed startups finish
or be reconciled while DB scheduler replicas still run. Then set
`OMNIGENT_FEATURES=-automations_v2` and restart all scheduler replicas.
Legacy startup clears persisted cursors so a later re-enable initializes future
occurrences instead of replaying work that timers already handled.
Changing the environment of a running server does not stop admission or switch
its scheduler; this release flag is not a live pause control.

Running sessions are not expired by this scheduler; their existing
completion hook and stale-run backstop remain responsible for terminal status.

Run the focused checks from the repository root:

```sh
.venv/bin/pytest tests/server/scheduled tests/stores/test_scheduled_task_store.py \
  tests/server/integration/test_scheduler_lifespan.py \
  tests/server/integration/test_scheduled_tasks_routes.py tests/db/test_enum_codecs.py \
  --reruns 0 -q
```

These use real database transactions with fake fire callbacks. They cover replica
races, rollback, task edits, tenant isolation, leases, interrupted startup, server
lifespan and CRUD responses under the scheduler switch. The same store/dispatch
tests accept `OMNIGENT_TEST_DB_URI` for live PostgreSQL, MySQL or CockroachDB.

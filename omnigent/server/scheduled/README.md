# Persistent task scheduling

`PersistentTaskScheduler` stores scheduling progress in the database so tasks can
survive server restarts and multiple servers can share the work.

The shared backend and UI flag `automations_v2` selects this scheduler. It defaults
to off, which keeps the existing in-memory timers. Keep it off until the execution
callbacks described below are connected; the standalone server does not supply
those callbacks yet.

## How a task starts

1. The scheduler finds active tasks whose `next_run_at` has arrived.
2. The store locks and rechecks the task, creates a `starting` run, and saves the
   next future run time in one transaction. This reserves the occurrence, also
   called claiming it. Another replica cannot create the same occurrence again.
3. The scheduler calls `on_fire(task, lease)` to prepare the session and send the
   prompt. While that callback works, the scheduler renews the run's startup lease.
4. The callback records `running` once the prompt is sent. Session completion and
   stale-run checks handle the eventual result of the turn.

After an outage, the scheduler starts one overdue occurrence per task and moves
its next run time into the future. For example, an hourly task last scheduled for
9 AM starts once when the server returns at 12:30 PM; its next run is at 1 PM.
It does not replay every missed hour. If a schedule edit revisits an occurrence
already in run history, the store advances the schedule without starting it again.

When this scheduler is enabled, creating a task or changing its schedule, time
zone, or state updates `next_run_at`. Prompt and run-history updates leave it
alone. Active tasks without a saved time start with a future occurrence; existing
saved times survive restarts. Each poll initializes one page of active tasks that
still lack a saved time. A failing row is retried on a later scan without blocking
other tasks or recovery.

Recurrences count from midnight on the task's creation date in its time zone.
That reference stays fixed across edits and restarts, including for `COUNT` and
`INTERVAL` rules. Invalid rules are paused if the task is still unchanged. Searches
that reach their time or work limit preserve the saved schedule for retry.

## If startup is interrupted

A startup lease is a renewable deadline stored on the run. Only the server
actively preparing that run renews it. Once it expires, recovery inspects the
session: the prompt may have arrived just before the server died, while the
database still says `starting`. Recovery preserves delivered work or cleans up
abandoned resources. It never resends the prompt.

Polling, renewal, and recovery run separately, so slow cleanup does not block due
tasks. Each server runs one poll and one recovery sweep at a time. Unresolved
cleanup is retried. Temporary renewal errors are retried only while the last
confirmed lease remains valid; expiry stops local startup. Shutdown cancels and waits for local work, leaving unfinished
startups to expire. A new host owner does not renew the old startup automatically.

Deleting a task hides it and prevents new scheduled runs. Unfinished claimed runs
and their task details remain for completion or cleanup. History is deleted in
small transactions, and recovery retries interrupted cleanup. The task row is
removed once no runs remain; finishing a run never purges a whole history in its
completion transaction.

## Configure timing and capacity

Add a `scheduled_task_scheduler` section to the server YAML config. These are the
defaults; omit any setting to keep its default:

```yaml
scheduled_task_scheduler:
  poll_seconds: 30       # Time between polls for due tasks and expired leases
  renewal_seconds: 30   # Time between startup lease renewals
  lease_seconds: 120    # How long a startup lease remains valid without renewal
  recovery_seconds: 30 # Timeout for one recovery attempt
  batch_size: 100       # Maximum rows fetched per database page
  max_startups: 100     # Maximum concurrent startups on each server
```

`create_app()` uses the existing server config loader, including `OMNIGENT_CONFIG`
for an explicit YAML path, unless the caller passes `server_config` directly.
Deployment wrappers can instead pass a `ScheduledTaskSchedulerConfig` from
[config.py](config.py) as `create_app(..., scheduled_task_scheduler_config=...)`.
That object overrides the entire YAML section; omitted fields use code defaults.

Settings are fixed when the app is created; restart to apply changes. All values
must be positive and finite, lease duration and capacities must be whole numbers,
and renewal must be shorter than the lease. Invalid or unknown scheduler settings
fail startup when `automations_v2` is enabled. With the flag off, the section is
ignored. Supplying settings does not enable the feature or supply execution hooks.

## Connect the execution callbacks

Pass `ScheduledTaskDispatchHooks` to
`create_app(..., scheduled_task_dispatch=ScheduledTaskDispatchHooks(...))`.
The callbacks supply execution, cleanup, and optional host ownership checks.

### `on_fire(task, lease)`

Use the supplied task snapshot and existing `lease.run`. Await the whole startup:

1. Call `await lease.check()` before each external startup action. This checks and
   renews the lease; if it raises, stop advancing startup.
2. After creating the session, call `await lease.attach_session(session_id)` before
   sending the prompt. Recovery needs this link to inspect delivery.
3. After sending the prompt, call `await lease.finish("running")`. For a known
   startup failure, finish with `"failed"` and its error details after cleanup
   succeeds. Leave uncertain outcomes or unfinished cleanup for recovery.

Keep work inside the callback and respect cancellation. An accepted external
request can still complete after cancellation; recovery must check its effects.

### `on_expired(run)`

Inspect the session and execution target, then return:

| What you find | Action and return value |
| --- | --- |
| The prompt was sent | Return `"running"`. |
| The prompt was not sent | Clean up unfinished resources, then return `"failed"`. |
| Delivery or cleanup is still uncertain | Return `None` or raise; a later sweep tries again. |

The scheduler updates the run only if its expired lease still matches. Cleanup
must tolerate repeat and concurrent calls, including resources another replica
already removed. External cleanup can still run concurrently even when the
database rejects a status update. Keep cleanup inside the callback and respect
cancellation and its timeout.

### `owns_host(workspace_id, host_id)`

Return whether this replica should process the occurrence or expired run. The
default is true. If hosts are assigned to replicas, return false for missing
assignments or unsupported hostless targets. Errors skip the row.

## Enable or disable the scheduler

First deploy the schema and code that understands `starting`, then connect and
test the callbacks. The old fire callback creates its own run and returns early,
so it needs adapting. The executor, Run now claiming, delegation, and sandbox
launch/cleanup are separate work. Integration must also handle sessions that finish
while their run still says `starting`; recovery currently only distinguishes
`running`, `failed`, or an unknown outcome.

Once those pieces are ready, set `OMNIGENT_FEATURES=automations_v2` and restart all
scheduler replicas together. Startup fails if the store or callbacks are missing.
Do not run old timers and the persistent scheduler against the same database at
the same time: the old timers do not reserve occurrences in the database.

To switch back, prevent new startups and let existing startups finish or recover
while the persistent scheduler is still running. Then set
`OMNIGENT_FEATURES=-automations_v2` and restart all replicas. The old scheduler
clears saved `next_run_at` values and calculates future timer times. Task
configuration and existing run history remain. Clearing these times does not
cancel running agent sessions. It prevents a later re-enable from replaying
occurrences the old timers already handled. Cursor clearing uses small transactions.
If clearing or timer startup fails, the server retries every 30 seconds. Timers
are exposed to task routes only after clearing and startup succeed.

The flag is read at startup and exposed through `/v1/info`. Changing a running
server's environment does not switch schedulers or pause work. Per-workspace
access controls are separate.

The store uses row locks on PostgreSQL, MySQL, and CockroachDB, and
`BEGIN IMMEDIATE` on SQLite. Cloudflare D1 is unsupported because its REST driver
cannot perform the required transaction across multiple statements.

## Code and tests

Start with [dispatch_scheduler.py](dispatch_scheduler.py) for the polling and
startup flow. [schedule.py](schedule.py) calculates future occurrences and their
identities. The [store](../../stores/scheduled_task_store/sqlalchemy_store.py)
implements the atomic database operations.

Run the focused checks from the repository root:

```sh
.venv/bin/pytest tests/server/scheduled tests/stores/test_scheduled_task_store.py \
  tests/server/integration/test_scheduler_lifespan.py \
  tests/server/integration/test_scheduled_tasks_routes.py tests/db/test_enum_codecs.py \
  --reruns 0 -q
```

Tests use real database transactions with fake execution callbacks. Store and
scheduler tests also accept `OMNIGENT_TEST_DB_URI` for PostgreSQL, MySQL, or
CockroachDB.

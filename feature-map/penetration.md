# Penetration Test — Strix reports

The scan icon after Load Testing opens a new independent page for the exact job.
Before a job exists, project context resolves to its latest job. Without either,
the page waits. Hover text explains the icon. New-job and existing-job composers
share the toolbar.

The page displays saved Strix run history, scan state, severity totals,
expandable findings, evidence, reproduction descriptions and remediation.
Severity filtering and JSON/HTML/CSV downloads use the displayed report.
Only Strix's explicit markers label a finding verified. Empty, missing,
interrupted or corrupt reports never imply a security pass. Unknown severity
is retained. Truncation is labeled and severity totals include the whole index.

Opening the dashboard starts a full-project Strix scan automatically. Run again
creates a fresh snapshot after the current scan finishes. Concurrent views reuse
an active scan. Stop scan revokes its inference credential and stops the worker.
Results refresh every five seconds, with history and exports retained per job.
Historical `run` links only view their selected result.

The server exports all saved project files, including uncommitted files, into a
private disposable snapshot; normal archive exclusions omit dependency caches,
Git metadata and Xwav runtime state. Strix may modify only the disposable copy.
Its pinned Python runtime is installed lazily and cached. A running Docker daemon
and the configured Xwav zero-cost model gateway are required; no separate Strix
login is needed. First use can download its sandbox image. Runs use full scope,
standard depth, 20 turns, a $1 engine budget and a 30-minute wall-clock limit.
Only zero-cost configured models are eligible; no paid fallback is enabled.
Missing tooling, exhausted capacity and incomplete results are reported as errors
or stopped scans, never as security passes. Project-local scope excludes remote
and production services. Source snapshots are removed when execution ends.

Only the job owner can start, stop or view results. Short-lived run credentials
can call only free inference, expire and are revoked on cancellation/completion;
they do not replace account credentials. Legacy workspace reports remain readable
from strix_runs/<run-name>/run.json plus vulnerabilities.json, or scan_data.json.
Linked/outside paths and oversized artifacts are refused.

## Verification

- tests/server/test_penetration_runtime.py covers current/legacy formats,
  missing, corrupt, oversized and linked artifacts, and quoted read-only transport.
- tests/server/routes/test_session_resources.py and
  tests/server/routes/test_shell_permission_gate.py cover workspace and owner
  binding, identifier validation and owner-only scan actions.
- web/src/pages/PenetrationPage.test.tsx and composer toolbar tests cover context,
  empty states, filters, evidence, downloads and icon ordering.
- tests/e2e_ui/sessions/test_xwav_workbench.py::test_penetration_report_dashboard
  covers desktop/mobile new-tab flow, actual runtime reading, live updates and
  downloads using isolated fixture reports. This does not claim a live scan.

- tests/server/test_strix_jobs.py covers full snapshots, active-run deduplication,
  fresh reruns, cancellation, disposable edits and revocable inference tokens.

Model request validation failures (400/413/422) preserve their non-retryable status.
After Xwav exhausts its bounded free-pool routing, scan-only requests return 424
so Strix's SDK does not replay the entire exhausted routing cycle. Other harness
requests retain normal capacity status codes. Failure messages classify bounded
logs without exposing prompts, credentials or raw upstream responses. Previously
saved generic failures are classified when viewed as well.

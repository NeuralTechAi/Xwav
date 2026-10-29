# Pre-Production Tests

The shield/check icon immediately after Preview opens an independent test dashboard
for the exact job, or the selected project's latest job. Hover explains its purpose.
Opening the page starts or resumes the latest report. A jobless page waits.

## Sub-features

- `run`: discover existing suites or use explicit project test configuration.
- `dashboard`: live category/platform results, commands, output and coverage gaps.
- `lifecycle`: keep running after closing the page, resume, stop and run again.
- `download`: export complete report data as JSON, HTML or CSV.
- `authorization`: only the workspace owner can execute checks or retrieve reports.
- `repair`: Fix issues sends the report's run reference to this job; ordinary chat
  requests mentioning dashboard failures also receive bounded, redacted report
  evidence automatically. Progress and file changes appear in the main chat.

## How to get to it (user POV)

Open any job composer and choose the shield immediately after the periscope. The
same icons appear on a project's New Job composer. Review categories and platforms,
expand output, download results, stop an active run or run again after source edits.

## Driving it with the repro environment

Preconditions: start the isolated environment from [Verify Omnigent](skills/verify-omnigent/SKILL.md) and
`tests/e2e_ui/sessions/test_xwav_workbench.py::test_preproduction_dashboard`.
The desktop/mobile journey runs real Python suites through the job, verifies
passing/failing checks and missing coverage, downloads a JSON report, reopens the
page, and cancels a new long-running check. Component tests verify context,
filters, exports and runtime failures. Runtime tests exercise persistent worker
transport, command reuse, failures, cancellation and timeout boundaries.

## Gotchas

Configured suites run as project code with the owner's existing job permissions.
They can create test artifacts or contact services according to their configuration.
Current host images include pinned Python Playwright, Chromium and axe-core, owned by Xwav rather than the project. Opening the dashboard does not install packages or change project files. Native emulators and credentials are not installed automatically.

Categories cover unit, integration, functional, regression, E2E, security, static
analysis/lint, usability, accessibility and smoke. Existing package scripts and
Python, Flutter and Android checks are discovered. A `.xwav/preproduction.json`
checks array explicitly supplies category, platform, argument-array command,
optional workspace-relative cwd and timeout (1–600 seconds). Explicit configuration
replaces discovery. Missing suites/tools are coverage gaps, never passes.

Built-in responsive Chromium baselines check HTTP/HTML, browser runtime errors,
horizontal overflow and viewport metadata at Web, Android and iOS dimensions.
axe-core uses the project copy when present, otherwise the image-owned copy. JavaScript syntax and npm lockfile dependency audits run automatically when applicable. Application-specific missing suites remain coverage gaps; the native `preproduction-tests` skill helps job agents register real suites. These are baseline checks, not complete application
flows, human usability reviews or native APK/IPA tests. Native iOS needs macOS/Xcode;
Android instrumentation needs an SDK/device and configured commands. Source secret
scanning is a limited baseline, not comprehensive vulnerability testing.

Results persist on the job host and survive page closure, not sandbox deletion.
Identical commands run once per report and expose reused results. Tests have bounded
time/output; the overall run is bounded to 30 minutes. Logs in downloads contain
up to the last 16000 bytes per command. Source changes during a run are flagged.
Passing checks do not certify production readiness or security.

Reports are not project test files. The owner-only `GET /sessions/{id}/diagnostics`
API reads existing Pre-Production, Load Testing, Strix and release reports without
starting a run. The agent receives failed check output/commands, metrics, findings,
build logs, run identity and source freshness only when requested. Missing reports
and infrastructure problems stay explicit. Saved coordinators supply verification
commands for test reruns; load verification is capped at 1000 requests. Publishing,
licence acceptance and credential setup keep their existing authorization rules.

Verification: `test_preproduction_dashboard` now drives a real failed suite through
Fix issues, confirms evidence reaches the model, observes a file repair in chat,
then reruns the coordinator and verifies the original failing check passes on
desktop and mobile. Native event forwarding is also tested for all four report
kinds in `test_dashboard_evidence_is_forwarded_to_native_chat`.

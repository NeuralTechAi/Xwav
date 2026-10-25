# Load Testing

The gauge icon immediately after Pre-Production Tests opens a separate page for
the exact job, or the selected project's latest job. Its hover text explains the
four profiles, controlled traffic, live metrics and downloads. A jobless page waits.

Opening the dashboard starts or resumes the job's report. Load, ramped stress,
spike/recovery and timed soak profiles run sequentially in the job runtime.
Closing the page leaves a bounded worker running; reopen to resume viewing.
Stop requests cancel the active profile and remaining work. Run again records a
new report. Concurrent views of the same job reuse its active run.

## Results

The responsive dashboard displays request counts, errors, throughput, sampled
latency p50/p95/p99, peak concurrency, elapsed time and a latency chart. Expand
platform evidence for Web/Android/iOS HTTP user-agent samples and raw time series.
Download JSON, HTML or CSV reports. Failures, timed-run budget exhaustion, runtime
errors and source changes remain visible. No missing result becomes a pass.

## Configuration and limits

No external service, browser, emulator or load-testing package is required.
The existing preview discovers the owner's local app endpoint. Targets are
loopback-only; only local-path GETs are allowed and redirects are not followed.
The default run is about one minute, capped at 16 concurrent connections,
20 requests/s and 2000 total requests. Each response samples up to 16 KiB of body;
latency includes connection, headers and that sample, not a full page render.

`.xwav/loadtesting.json` configures paths, concurrency, max_concurrency,
requests_per_second, max_requests, max_p95_ms, max_error_percent and durations
(load, stress, spike, soak). Hard ceilings are 16 concurrency, 50 requests/s,
100,000,000 requests. Timed mode allows 120 seconds per short profile and 1800 seconds soak. A longer
endurance run needs a sufficient request budget. A 30-second default soak is a
short endurance baseline, not hours of stability proof. Thresholds default to
p95 <= 1000 ms and errors <= 1%. App-specific authenticated workflows and native
rendering/device tests need project tooling. Published remote endpoints are not
supported by this local runner. Results never certify production capacity.

## Verification

`tests/server/test_loadtesting_runtime.py` exercises real traffic, metrics,
validation, waveforms, budget exhaustion, errors, persistence and cancellation.
The owner-only shell transport is shared with pre-production reports and covered
in `tests/server/routes/test_session_resources.py`. Dashboard tests cover job and
project context, jobless state, actions, failures and downloads. Composer tests
verify icon ordering, tooltip and independent-page context.

`tests/e2e_ui/sessions/test_xwav_workbench.py::test_loadtesting_dashboard` follows
the composer icon through a real worker, all profiles, downloads, reopening and
cancellation at desktop/mobile widths using isolated fixture workspaces.

The Load Testing dashboard accepts a Total requests value from 1 to 100,000,000.
Run again sends exactly that total, divided between the four profiles. Any remainder
is allocated one request at a time in profile order. Totals below four skip profiles
with zero allocation. Requests include failed attempts; errors are reported separately.
Count-driven phases advance their traffic pattern by request progress rather than time.
They finish their allocation instead of stopping at the old duration limit. Large
counts may take hours or days at the configured rate; Stop cancels with the actual
partial count. A heartbeat detects stalled workers without expiring healthy long runs.
Automatic initial reports retain the configured timed-baseline mode; the dashboard
labels older timed reports and asks users to rerun for an exact selected total.
Set request_mode to count in the project configuration to use exact counts initially.
Counters are exact; latency percentiles use a bounded reservoir of up to 4096 samples
per profile/platform and time series retain at most 1800 points.

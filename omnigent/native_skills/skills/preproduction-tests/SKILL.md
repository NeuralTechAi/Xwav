---
name: preproduction-tests
description: Prepare application-specific test suites for Xwav Quality Lab, register coverage categories, and resolve pre-production coverage gaps.
user-invocable: true
---
# Xwav pre-production tests

Use this workflow when building an application that will be verified through the
composer's Pre-Production Tests icon, or when the user asks to close coverage gaps.

Inspect existing tests and package scripts first. Reuse suites; do not install a
second test framework when the project already has one. Add assertions for the
app's real behaviour, including error recovery and keyboard/touch interactions.
A page-loading check cannot substitute for integration, regression or E2E flows.

Quality Lab automatically discovers these package scripts: `test:unit`/`test`,
`test:integration`, `test:functional`, `test:regression`, `test:e2e`/`e2e`,
`test:security`/`security`, `lint`, `typecheck`/`type-check`,
`test:a11y`/`test:accessibility`, `test:usability`, and `test:smoke`.
Use noninteractive commands that terminate. Keep Node test discovery from loading
Playwright specs unintentionally. Give browser suites their own test server and
port; do not terminate or reuse another job's server.

For custom commands/platforms, write `.xwav/preproduction.json`:

```json
{"checks":[
  {"name":"Arithmetic unit tests","category":"unit","platform":"shared","command":["npm","run","test:unit"],"timeout":180},
  {"name":"Web checkout workflow","category":"e2e","platform":"web","command":["npm","run","test:e2e"],"timeout":180}
]}
```

Explicit configuration replaces automatic discovery; include all intended suites.
Supported categories are unit, integration, functional, regression, e2e, security,
static, usability, accessibility, smoke. Platforms are shared, web, android, ios.
Commands are argument arrays, cwd stays in the workspace, timeout is 1–600 seconds,
and the checks array has at most 40 entries. Never map one generic suite to all
categories to make the report green.

Current Xwav host images include Python Playwright, Chromium and axe-core at
`/opt/xwav-quality/node_modules/axe-core/axe.min.js`. Built-in browser baselines
use these without adding project dependencies. Project Playwright test suites
still need their own matching framework/browser version; do not assume a bundled
Chromium revision matches arbitrary Node Playwright versions. Missing tools on
older/custom hosts remain blocked until that host is upgraded.

Run the real suites, fix failures, then use Run again in Quality Lab. Review each
category and downloaded evidence. Responsive Chromium Android/iOS viewports test
web layouts, not native apps or Safari. Register separate SDK/device commands for
native projects. Automated axe/usability checks supplement human review. Report
unsupported coverage and missing credentials explicitly; never turn gaps into
passes or claim production/security certification.

## Load Testing

The gauge icon after Pre-Production Tests opens the native Performance Lab for
the same job. It uses Python's standard library and runs local read-only HTTP
GET requests with bounded concurrency, rate, response sampling and request count.
The four profiles are steady load, ramped stress, spike/recovery and timed soak.
Configure `.xwav/loadtesting.json` with local `paths`, `concurrency`,
`max_concurrency`, `requests_per_second`, `max_requests`, `max_p95_ms`,
`max_error_percent` and `durations` (load/stress/spike/soak seconds).
Limits are 16 concurrent requests, 50 requests/s, 100,000,000 requests/run, 120 seconds
per short profile and 1800 seconds soak. Choose a sufficient request budget for
longer runs; exhaustion is reported as incomplete coverage. Mobile user-agent
samples measure the shared backend, not native rendering. Use a quiet workspace
and compare repeated runs before making capacity claims.

The dashboard's Total requests field accepts 1–100,000,000. Run again divides
and sends that exact total across the four profiles; it does not stop at the timed
baseline durations. Failed attempts count toward the total and remain errors.
Rate/concurrency limits stay active, so large totals may take hours or days.
Stop preserves the actual partial count. Set request_mode to count in configuration
for exact-count runs on initial opening too. Healthy count runs use heartbeat
supervision rather than the timed-run deadline. Counters, latency samples and time
series stay bounded in memory regardless of the selected request total.

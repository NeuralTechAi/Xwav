# Plans, BYOK and subscription gateway

Entry points:
- Main workbench rail → Plans & Models (immediately before Search), Settings sidebar
  → Plans & models, and direct `/settings/billing`.
- Annual toggle, Teams quantity, Checkout and customer portal.
- Provider/model/mode selection, encrypted key save/remove, team invite/accept/remove.
- Gateway token create/rotate/revoke, agent bundle download and Custom agents import.
- `xwav billing init` / `validate` for operator setup.
- `/v1/inference/{mode}/models` and Chat Completions / Responses / Messages endpoints.
- Stripe signed webhook, independently authenticated from the browser.

Native operator setup and usage semantics: [SUBSCRIPTIONS.md](../docs/SUBSCRIPTIONS.md).
Default plan definitions: `omnigent/billing/plans.json`. Changes require a server restart.
The server caches the SPA HTML entry page at startup. After rebuilding the web UI,
restart the running Xwav server as well; browser refresh alone can keep loading an
older asset entry point. Preserve its existing database, environment and arguments.
One-node/one-worker deployment only; this optional gateway does not replace existing
vendor CLI login paths. No billing keys are configured by default.

Verification:
- `tests/billing/test_subscriptions.py`: actual route contracts, scoped tokens/keys,
  data encryption, signature/replay handling, annual checkout, team entitlement,
  queue priority, atomic quota reservation and final streaming usage, failures,
  CLI setup, parseable download and native upstream protocols. Scripted HTTP upstreams.
- `web/src/shell/WorkbenchRail.test.tsx`: rail placement before Search, tooltip,
  billing navigation and active state.
- `web/src/pages/settings/SettingsBillingSection.test.tsx`: UI pricing, annual totals,
  credit tiers and safe key input clearing. `settingsNav.test.tsx` covers shared nav.
- `tests/browser_ui/test_billing.py`: built-SPA navigation, annual prices and BYOK
  submission; reuses the existing appearance shell contract. No external network.
- Native job use: parseable agent and model HTTP transport are covered separately.
  Full live harness/model, Stripe purchase/portal interaction and delivered Stripe
  webhook require configured deployment credentials; not proven by mock tests.

Browser evidence should be captured outside the repository. Never use an existing
user server for the test. The browser-contract fixture serves this candidate build
on a private port and denies unregistered same-origin API calls.

FreeLLMAPI: `xwav billing connect-freellmapi` verifies approved available models
and connects a separate loopback-only gateway. See
[deployment and live-test evidence](../deploy/freellmapi/README.md).
`tests/billing/test_freellmapi.py` covers catalog gating, private credential files,
duplicate avoidance and preserving the active configuration on failure.

Automatic Free/subscription Docker jobs: new-job model preview and session creation bind the
selected compatible harness to Xwav's gateway. `tests/billing/test_jobs.py` covers
all declared adapters' nonsecret bindings, private job-token scope/revocation,
selected-harness-only readiness, native output limits and protocol routing.
`tests/server/test_sandbox_inference_routes.py` retains explicit-provider policy
and pre-persistence validation coverage. Live native process evidence is recorded
separately from these scripted contracts. Existing sessions keep prior bindings.

Free recovery: `tests/billing/test_failover.py` exercises zero-cost model and
provider switching, Auto priority, proactive low-headroom cooldowns, all three
stream protocols, partial-tool suppression, local quotas, cancellation,
timeouts and the authenticated HTTP route. Only complete buffered attempts reach
the harness. Exhaustion returns Retry-After, never a paid-model fallback. The
Plans & models page explains the delivery tradeoff when failover is enabled.

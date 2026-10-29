# Native subscriptions and model gateway

Xwav has an optional, single-node subscription gateway at Settings → Plans & models
(`/settings/billing`). It uses HTTPX, SQLite/SQLAlchemy, and the existing cryptography
dependency. No Stripe SDK, LiteLLM service, or per-provider SDK installation is required.
`max_inflight` (default 4) and `queue_limit` (default 32) bound concurrency and memory.
Existing provider CLI subscriptions are independent; they never become Xwav paid credits.

## Included plans

| Plan | Monthly | Annual payment | Monthly allowance |
| --- | --- | --- | --- |
| Free | $0 | — | 1,000 requests to operator-approved free models |
| Pro | $25 | $216 ($18/month equivalent) | 10 million input + output tokens |
| Teams | $30/member | $324/member ($27/month equivalent) | 10 million tokens per member |
| Max | $200 | — | 1,000 credits ($50 configured model usage) |
| Scale | $500 | — | 2,500 credits ($125 configured model usage) |
| Scale | $900 | — | 5,000 credits ($250 configured model usage) |
| Scale | $1,800 | — | 10,000 credits ($500 configured model usage) |

Max/Scale use cost-weighted credits: the initial conversion is **1 credit = $0.05
of configured provider API usage**. Pro and Teams use tokens instead. All prices,
model rates and limits live in JSON, independent of provider/model releases.
No silent paid overages, automatic top-ups, or daily token cap. A monthly request
ceiling is an abuse safeguard, configurable separately from the token allowance.
Pro/Teams unused **base** tokens roll into the next month only; previously rolled
tokens expire. Annual payments still grant/reset tokens monthly, on the subscription
anniversary day (including short-month handling). The gateway gives active paid
subscriptions priority in its bounded local inference queue; it cannot change an
upstream vendor's queue priority.

Team subscriptions use Stripe quantity for purchased seats. The purchaser owns
one seat, invites exact Xwav account IDs, and members must accept in their own
settings. Each member has a separate allowance. Removing a member or canceling
immediately revokes the subscription entitlement. Existing Xwav project sharing
and workspace permissions remain the collaboration controls; membership alone
never grants project access or shares API keys. Additional seats must be purchased
in the Stripe portal before invitations can be allocated. When seat count shrinks,
only the first remaining allocated members (account-ID order) keep entitlement.

## Configure an installation

1. Run `xwav billing init --directory /private/path/billing --public-url https://xwav.example`.
   This creates `plans.json` and a private `billing.env` with a generated encryption key.
   It refuses to overwrite existing setup. Keep the encryption key in the deployment's
   secret manager and back it up; losing it makes saved BYOK keys unreadable.
2. Load `billing.env` into the **server** environment. Set `XWAV_STRIPE_SECRET_KEY`
   to a Stripe **test** secret and `XWAV_STRIPE_WEBHOOK_SECRET` to its endpoint secret.
   For launch, live keys additionally require `XWAV_BILLING_LIVE=1`.
3. Create USD recurring Stripe Prices matching the table above. Annual Prices charge
   12 months upfront. Set the `XWAV_STRIPE_PRICE_*` environment variables named in
   `plans.json`. Teams Prices support adjustable quantity. Configure customer portal
   products, cancellation, quantity changes and allowed upgrades/downgrades in Stripe.
   The server verifies each checkout price matches the displayed USD amount and interval. Stripe remains the
   payment authority. Taxes are handled by your Stripe configuration, not computed here.
4. Register `/v1/billing/webhook` for `checkout.session.completed` and
   `customer.subscription.created`, `.updated`, `.deleted`. The server verifies
   raw-body HMAC signatures with a five-minute tolerance, re-fetches authoritative
   subscription state, and applies events idempotently. Browser success redirects
   never grant paid access. Failed/past-due/canceled/expired subscriptions lose access.
5. Add approved models and managed provider key **environment references** to `plans.json`.
   Native provider presets cover OpenAI, Anthropic, Google, xAI/Grok, DeepSeek and Mistral.
   Exact model IDs and their prices are curated by the operator rather than hardcoded
   into a release. Restart after changing the registry.
6. Run `xwav billing validate /private/path/billing/plans.json`, then restart Xwav.
   The page remains explicit about missing configuration until setup is complete.

A model entry inside a provider's `models` array:

```json
{
  "id": "friendly-model-name",
  "upstream": "exact-model-id-from-provider",
  "protocol": "chat/completions",
  "input_usd_per_million": 0.5,
  "output_usd_per_million": 2,
  "max_output_tokens": 4096,
  "free": false
}
```

Prices are USD per million tokens, including fractional rates. For newer reasoning
models, set `output_token_field: "max_completion_tokens"` when required; the gateway
preserves that field instead of converting it to the legacy `max_tokens`. Configure conservative
rates where provider pricing varies by context size; cache reads are conservatively
priced at the configured input rate and Anthropic cache writes at twice that rate.
A new compatible provider requires one JSON entry with an ID, label, operator-owned
base URL, key environment variable and model list. Models use Chat Completions,
Responses, or Anthropic Messages; no wire conversion or unsupported harness fallback
is attempted. Google uses its documented OpenAI-compatible surface. Protocol-specific
features retain upstream limitations.

## Free models

The local FreeLLMAPI deployment, connection command and live verification are
documented in [the FreeLLMAPI deployment guide](../deploy/freellmapi/README.md).


Point a `free-gateway` provider at an operator-approved OpenAI-compatible gateway
(FreeLLMAPI-compatible, Ollama, vLLM, or another service), add models with `free: true`,
and set a credential environment variable. A credential is required even for a local
endpoint: a dummy value works only if that endpoint permits it. Truly zero-priced
models use zero rates; sponsored paid models require a nonzero Free plan allowance.
The shipped Free allowance is 1,000 requests per UTC month, with no managed cash
allowance. FreeLLMAPI itself is not vendored or started, and personal free-tier keys
are not pooled. Verify the chosen provider's terms before offering a public service.

## Using a profile in a job

1. Select Free, Subscription or BYOK, select a provider/model, and save.
2. For BYOK, save your provider key in Settings. It is encrypted, owner-bound and
   never returned to the browser, job agent or downloadable configuration.
3. Create a gateway token. Set `XWAV_GATEWAY_TOKEN` in the job host environment.
   Download the Chat Completions agent bundle and import it in Custom agents;
   choose that agent in New Job. The bundle contains an environment reference,
   never a credential. The server's public URL must be reachable from that host
   or sandbox; a sandbox's `localhost` is not the host/server.
4. Other compatible harnesses can use `/v1/inference/{free|managed|byok}` as their
   base URL, the gateway token as their credential, and `provider-id/model-id` as
   their model. Configure the harness's correct API protocol. The native model
   listing endpoint is `GET .../models`. No existing jobs are silently rewritten.

Gateway tokens authorize spending up to that account's allowance, are shown once,
and can be rotated/revoked. Rotating invalidates the previous token. Treat them
as secrets; revoke them when removing account access. Browser-only native job
credential provisioning is not added by this module: hosts must receive the gateway
credential through their existing secret configuration. Vendor CLI OAuth remains
available outside these managed gateway plans.

## Accounting and operating limits

Before inference, a transaction reserves conservative input-byte/output-token bounds.
Concurrent requests cannot all spend the same balance. Final usage settles actual
input/output tokens; reported cached Anthropic input is also charged. A rejected
upstream request releases its reservation but still counts as an attempted request.
Timeouts, interrupted streams and missing final usage retain the reservation to
avoid falsely reporting free usage. Reconcile uncertain reservations against the
provider invoice before manually adjusting the ledger. Recorded model costs are
usage estimates at your configured rates, not an upstream invoice guarantee.

BYOK never falls back to operator keys, never consumes paid credits, and has a
separate one-million-request monthly abuse ceiling (`byok_request_limit` in JSON). Managed
billing currently permits text and client-executed function tools. Images, audio,
vendor-hosted tools, background jobs, previous-response state and paid service-tier
upgrades are rejected until explicit metering is implemented. BYOK may use richer
provider features at the user's own provider bill.

Deploy **one server worker on one node**, with the SQLite ledger on persistent
private storage. Cross-worker payment serialization, distributed queues, organization
invoicing and automatic provider invoice reconciliation require a shared transactional
billing service before a multi-node rollout. Use HTTPS outside loopback, account auth
for public installations, a private encryption key, and operator-controlled URLs.
This release does not lock existing open-source features behind a subscription,
promise provider capacity, implement a new DNS service, or alter generated-app branding.

## Verification

- `pytest tests/billing -q --reruns 0`: scripted provider/payment transports,
  actual HTTP routes, streaming, encryption, tenant isolation, signatures/replay,
  token/cost limits under contention, monthly rollover, annual billing, seats and CLI.
- In Settings → Plans & models: switch annual billing, inspect annual totals,
  save/remove a test BYOK key, and verify the key field clears after submission.
- With a Stripe test setup, complete Checkout, deliver the signed webhook, refresh,
  then cancel through the portal and verify managed inference is denied.
- Create the gateway agent on a test host, ask it to read a disposable project file,
  and verify the selected model and correct usage bucket increment.

No live provider calls, Stripe purchases, DNS changes or store deployments are
needed for the automated regression suite. Live financial/provider readiness must
be checked with the installation's actual accounts before launch.

## Automatic Free sandbox jobs

New local Docker jobs with no explicitly configured agent/operator provider use the
account's Free model selection automatically. The model picker previews the
configured registry locally, without provisioning a container or probing vendor
login services. No vendor account, API key, manual token generation or agent
bundle import is needed for this path.

Supported provider-bound adapters are Pi/Pi native, Claude SDK/native, Codex/native,
OpenAI Agents, Qwen, OpenCode native and Jcode. They use Chat Completions, Responses
or Messages as appropriate. FreeLLMAPI must support the configured protocols.
Vendor-only clients such as Cursor, Copilot and Kiro retain their vendor account
requirements; unsupported choices are rejected before provisioning. Harness² is a
benchmark workflow, not an interactive chat harness. This is not a claim that a
free model reproduces a proprietary vendor model's behavior or capabilities.

A fresh local Docker sandbox receives a private inference-only credential file, with no vendor
keys and no inherited Codex login on the automatic Free path. The encrypted token
is bound to the sandbox host's current launch credential. Every request checks
host revocation/expiry and permits only Free usage, charged to the host owner's
existing quota. Removing/replacing the managed host credential revokes access.
Saved session snapshots contain a command that reads the private credential file;
they never contain the credential. Explicit agent auth, operator inference profiles
and BYOK choices are preserved. Existing jobs retain their prior bindings.

Native output requests are bounded to the configured Free model maximum. Responses
jobs advertise only client-side function tools to the text-only free router;
hosted/custom tools are omitted. Function schemas may use field names such as
`source`; actual media attachments remain blocked under text-only managed billing.

Each job still owns its own sandbox. Startup checks only its bound harness binary,
rather than every unrelated CLI and vendor login. The Docker overlay build has a
source-only context to avoid sending runtime secrets or dependency trees to the
builder. No SDK download or image rebuild occurs during ordinary job startup.

Subscription jobs use the same automatic binding and private credential mechanism
when the account selects Subscription mode. Their tokens are scoped to `managed`,
Free job tokens to `free`; neither can switch modes or bypass subscription status,
provider availability or usage limits. No harness is excluded because of its
pricing tier. Provider protocol compatibility and proprietary CLI account
requirements still apply. Native Qwen receives its OpenAI-compatible job endpoint,
model and scoped Xwav credential automatically.

The Free allowance is now **1,000 requests per user per UTC month**. This changes
Xwav's application allowance, not anonymous upstream capacity or rate limits.

Local live verification: Pi native, Claude native, Codex native, OpenCode native,
native Qwen and the OpenAI Agents SDK returned the expected synthetic reply with
no vendor account keys. The SDK also passed using a separately activated test
subscription and a zero-cost model; no live Stripe payment was made. Observed
ready times were about 16–33 seconds in the final checks, with model replies later;
shared free-provider latency/rate limits still apply. A 218-check backend regression
run and 24 targeted gateway checks passed. The broader host suite passed 462
checks, with eight older tests failing on existing branding/native-skill assumptions.

### Free model failover

The zero-cost Free pool, on Free or active subscription profiles, has bounded automatic recovery across registered free
models and providers with configured credentials. Auto follows its approved
candidate order; a selected concrete free model is preferred first. Retryable
upstream errors (capacity, quota exhaustion, unavailable models, connection
failures and interrupted streams) put a route on cooldown and advance to the
next compatible, zero-priced model. Explicit low-headroom response headers also
cool a route before the next call. FreeLLMAPI remains responsible for its own
per-key usage tracking and upstream quota forecasts; unknown future provider
quota changes cannot be predicted.

Free stream attempts are buffered up to 2 MiB and must have a successful protocol
completion before delivery. Partial text or tool calls from a failed attempt
are discarded; Xwav never splices them into another model's answer. This adds
latency before the first visible text but avoids replaying delivered tool calls.
The default budget is eight attempts, 45 seconds per attempt and 120 seconds
in total, with a 60-second cooldown unless an upstream supplies Retry-After.
Configure `free_failover`, `free_failover_max_attempts`,
`free_attempt_timeout_seconds`, `free_failover_timeout_seconds` and
`free_failover_cooldown_seconds` in the operator's billing registry.

Retries count as one logical user request. Token reservations and local plan
allowances still apply to each attempt; ambiguous usage remains conservatively
reserved. Local authorization, validation and quota failures do not trigger
provider switching. Paid model and BYOK requests keep their explicit provider/model;
Free recovery never spends paid credits or uses a customer's BYOK key. If all
configured free routes are exhausted, Xwav returns a sanitized 503 with a
Retry-After delay. There is no guarantee of unlimited free upstream capacity.

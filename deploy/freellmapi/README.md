# Optional local FreeLLMAPI service

Xwav's Free plan can use a separate, loopback-only FreeLLMAPI server. This is
installed once, not once per job. Xwav retains ownership, request quota and
credential isolation; FreeLLMAPI handles upstream routing and cooldowns.

Xwav bridges client-executed Responses custom tools, including Codex's freeform
`apply_patch`, through an explicit function schema with one `input` string.
It also reads deferred `additional_tools` inventories and preserves namespaces,
including Codex's JavaScript executor that calls `tools.apply_patch` internally.
It restores native custom-tool calls and streamed input events on the way back,
and normalizes their history on the next request. This keeps patch text out of
invented command-array wrappers. Models whose Codex metadata does not register
`apply_patch` receive an explicit capability note directing them to the available
`exec_command` schema instead. Tool permissions and sandbox enforcement stay
with the harness.

The reviewed upstream is [tashfeenahmed/freellmapi](https://github.com/tashfeenahmed/freellmapi),
commit `22b7ec74a09892d3efdb9107ec3e74c764dd71a1` (MIT). The current local installation
lives in the ignored `.omnigent/services/freellmapi` directory. Source is not vendored
into Xwav's Python package. The desktop and frontend workspaces are not installed.

The server was installed using Node 24.11 and npm workspaces:

```sh
npm ci --ignore-scripts --workspace @freellmapi/server --workspace @freellmapi/shared --include-workspace-root=false
npm rebuild better-sqlite3
npm audit fix --ignore-scripts --workspace @freellmapi/server --workspace @freellmapi/shared --include-workspace-root=false
npm run build --workspace @freellmapi/server
```

The installation applies compatible security dependency updates to the upstream
lockfile before compiling. Keep its resulting lockfile with the runtime's backup.
At verification, the server-scoped production audit had **no critical advisories**
and one remaining high Zod advisory, GHSA-mrhx-c7xc-m3w5. A forced Zod 4 upgrade is
not applied to upstream code written against Zod 3. This is a local-development
installation, not a production hardening certification. Loopback binding, unified-key
authentication, request-size/rate limits and a 384 MB service memory limit reduce
exposure; upgrade upstream and re-audit before a public commercial rollout.

## Current backend

Only OVHcloud's documented anonymous tier is enabled; there are no paid provider
keys. Its published cap is two requests per minute per IP/model and availability
is shared/capacity-dependent. Do not add authenticated OVH billing credentials
and assume they are the same free tier.

Private `server/data/xwav-config.json` uses FreeLLMAPI's declarative configuration
to create its local administrative account, add an OVH keyless sentinel, and
register these real upstream models:

The configured priority order (verified 2026-10-27) is:

| Display name | Xwav / FreeLLMAPI ID | Real OVH upstream ID |
| --- | --- | --- |
| GPT-OSS 120B | `gpt-oss-120b` | `gpt-oss-120b` |
| Qwen 3.8 27B | `qwen-3.8-27b` | `Qwen3.8-27B` |
| Qwen 3.5 397B A17B | `qwen-3.5-397b-a17b` | `Qwen3.5-397B-A17B` |
| Qwen 3.6 27B | `qwen-3.6-27b` | `Qwen3.6-27B` |
| GPT-OSS 20B | `gpt-oss-20b` | `gpt-oss-20b` |
| Qwen 3.5 9B | `qwen-3.5-9b` | `Qwen3.5-9B` |
| Llama 3.3 70B | `llama-3.3-70b` | `Meta-Llama-3_3-70B-Instruct` |
| Mistral Small 3.2 | `mistral-small-3.2` | `Mistral-Small-3.2-24B-Instruct-2506` |

This is an operator-selected routing order, not a comparative benchmark ranking.
Auto uses a single candidate per attempt and skips unavailable/cooling-down models.
The local service uses its declarative fallback chain (active profile cleared via
`POST /api/profiles/active` with `{"profileId": null}`), so an older named profile
cannot silently override the order. Gateway administrators must keep the displayed
pool in sync whenever they change the active routing chain.
The Plans & models page lists the complete configured pool when Auto is selected.
Transient upstream availability can change after verification.

FreeLLMAPI's compatibility aliases labelled Claude are not exposed as Claude
models in Xwav. Xwav imports only `auto` and the eight approved concrete aliases.
New gateway models are not silently added to the Free offering.

The private service environment sets:

```text
NODE_ENV=production
HOST=127.0.0.1
PORT=4000
FREEAPI_DB_PATH=/absolute/private/path/freeapi.db
FREEAPI_CONFIG_PATH=/absolute/private/path/xwav-config.json
ENCRYPTION_KEY=<generated 32-byte hex key>
CATALOG_SYNC_DISABLED=1
IMAGE_NORMALIZE=off
REQUEST_BODY_LIMIT_MB=2
PROXY_RATE_LIMIT_RPM=10
ADMIN_RATE_LIMIT_RPM=30
ALLOWED_HOSTS=127.0.0.1,localhost
```

The SQLite database, administrative password, encryption key and unified API key
are private files; never commit or print them. Source dependencies do not need
read access to Xwav's provider keys. The gateway is not exposed to the LAN.

For Linux, install the example unit with real absolute paths as a **user service**.
The running installation uses `xwav-freellmapi.service`:

```sh
systemctl --user status xwav-freellmapi.service
systemctl --user restart xwav-freellmapi.service
systemctl --user stop xwav-freellmapi.service
```

## Connect it to Xwav

Save the gateway's generated unified API key to a private file (0600), then run:

```sh
xwav billing connect-freellmapi \
  --config /private/path/billing/plans.json \
  --url http://127.0.0.1:4000/v1 \
  --key-file /private/path/unified.key \
  --model auto --model qwen-3.8-27b --model gpt-oss-120b \
  --model qwen-3.5-397b-a17b --model qwen-3.6-27b \
  --model gpt-oss-20b --model qwen-3.5-9b \
  --model llama-3.3-70b --model mistral-small-3.2 \
  --auto-model qwen-3.8-27b --auto-model gpt-oss-120b \
  --auto-model qwen-3.5-397b-a17b --auto-model qwen-3.6-27b \
  --auto-model gpt-oss-20b --auto-model qwen-3.5-9b \
  --auto-model llama-3.3-70b --auto-model mistral-small-3.2
```

`--auto-model` records an explicit operator-verified routing pool for display; it
must match the gateway's configured enabled fallback chain. It does not reconfigure
the external gateway. Each candidate must also be an approved `--model` entry.
Omitting these flags leaves the pool undisclosed rather than guessing its members.

The command checks `GET /v1/models?available=true`, rejects unavailable IDs, and
preserves other providers/plans. It stores only the gateway's unified key in the
private `billing.env`; it does not import upstream vendor keys. Load that file
into the Xwav server environment and restart the server. Re-running replaces the
same provider instead of creating duplicates. Existing jobs keep their configured
provider; select the Free gateway profile for new jobs.

Xwav's Free limit remains 1,000 requests per user per UTC month. Anonymous upstream
capacity is separate and may be exhausted first. More users do not create more
upstream quota. For sustained service, add a provider/account whose terms and
capacity permit your intended use, or provision a self-hosted backend.

## Verified behavior

Real synthetic requests passed through Xwav → FreeLLMAPI → OVH: non-streaming
Llama text, Mistral SSE streaming, and a bounded two-request agent SDK tool flow
(one required tool call followed by model confirmation of its result).
Xwav recorded real token usage and zero managed cash spend. Test tokens belonged
to separate verification identities and were revoked afterwards. No user project
files or paid model keys were used. Re-run live tests sparingly within upstream
limits; unit tests in `tests/billing/test_freellmapi.py` use scripted transport.

The live agent verification returned `XWAV_TOOL_OK_42`, executed its synthetic
project-reading tool once, and recorded 200 tokens across two requests with zero
managed cash spend. An earlier unconstrained trial skipped its tool, and a
repeated-tool trial hit anonymous capacity. Model behavior and upstream capacity
are limitations; this is not a claim that every autonomous coding task succeeds.
Capacity errors now preserve HTTP 429/503 and bounded Retry-After headers in Xwav,
rather than being reported as a generic 502.

The six newer candidates above passed direct anonymous arithmetic and required
structured tool-call probes with the expected arguments. These small correctness
checks establish transport/tool compatibility, not general coding superiority.

All eight concrete models also passed real streaming Python-function generation
through Xwav → FreeLLMAPI → OVH. The generated source was inspected as an AST,
not executed. The verification identity recorded zero managed cash spend. Qwen
3.8 initially stalled during streaming and passed a later bounded retry; shared
anonymous capacity remains variable. GPT-OSS 120B is first in Auto's priority
chain based on these compatibility/latency checks, not a broad quality benchmark.

A real GPT-OSS 120B agent SDK round trip executed a synthetic tool once and
confirmed its result (`XWAV_TOOL_OK_42`), recording 335 tokens across two requests
and zero managed cash spend. A separate Auto request selected `gpt-oss-120b`,
streamed the expected Python function and recorded 164 tokens at zero spend.
Disposable verification gateway tokens were revoked afterwards.

Xwav now adds zero-cost Free recovery around this upstream gateway. A concrete
selection can advance through approved free alternatives when capacity is low
or a stream fails. Complete attempts are buffered before reaching a harness,
so upstream mid-stream errors cannot mix answers or replay delivered tools.
Paid models are excluded. Configure the bounded attempts, deadlines and
cooldowns in Xwav's billing registry (see `docs/SUBSCRIPTIONS.md`). FreeLLMAPI's
own quota tracking still applies, and aggregate free capacity can be exhausted.

## Tool-calling compatibility

The native FreeLLMAPI provider sets `omit_parallel_tool_calls: true`. The current
OVH backend rejects `parallel_tool_calls: false` with HTTP 400, including on
otherwise valid tool requests. Xwav omits that optional hint before forwarding;
function definitions, required tool choice and results remain intact. Other
providers keep the parameter unless the operator enables this compatibility flag.

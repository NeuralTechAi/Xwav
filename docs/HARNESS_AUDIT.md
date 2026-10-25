# Xwav harness architecture and readiness audit

Audit date: 2026-10-22. This inventories the existing adapters before the new
Harness² workflow contribution. It records supported contracts, not a claim that every
vendor account is signed in or that a live model turn was run.

## Shared architecture

`omnigent/harness_plugins.py` is the canonical contribution registry. Aliases
resolve to the same contribution; they are not separate installed harnesses.
`omnigent/harness_capabilities.py` declares integration, approval, instruction,
resume and model capabilities. The table below reads those declarations. A
capability declaration is not proof that a particular vendor release implements
it; the relevant adapter tests exercise the transport and lifecycle contracts.

- SDK adapters run in harness subprocesses using their vendor SDK. The label
  `sdk-in-process` describes the agent inside that subprocess, not the web server.
- CLI adapters launch headless vendor processes; ACP adapters speak JSON-RPC over
  stdio. Generic `acp:<slug>` entries use the same ACP executor and configured
  executable as the canonical `acp` contribution.
- Native TUI adapters coordinate resident terminal processes, history forwarders
  and MCP bridges. They require the terminal/tmux infrastructure and are blocked
  on Windows by readiness; use Linux/macOS or an explicitly supported environment.
- OpenCode native uses a runner-owned HTTP/SSE app server and a terminal attach
  client. Its accepted API version range is deliberately narrow.

## Canonical adapter matrix

| Canonical ID | Integration | Credential ownership | Approval bridge |
| --- | --- | --- | --- |
| `acp` | acp-subprocess | own-auth | sse-permission |
| `antigravity` | sdk-in-process | own-auth | none |
| `antigravity-native` | native-tui | own-auth | none |
| `claude-native` | native-tui | Xwav provider | hook |
| `claude-sdk` | sdk-in-process | Xwav provider | none |
| `codex` | cli-subprocess | Xwav provider | jsonrpc |
| `codex-native` | native-tui | Xwav provider | jsonrpc |
| `copilot` | sdk-in-process | own-auth | none |
| `cursor` | sdk-in-process | own-auth | none |
| `cursor-native` | native-tui | own-auth | approval-mirror |
| `devin-native` | native-tui | own-auth | hook |
| `goose` | acp-subprocess | own-auth | sse-permission |
| `goose-native` | native-tui | own-auth | approval-mirror |
| `grok` | acp-subprocess | own-auth | sse-permission |
| `hermes` | cli-subprocess | own-auth | hook |
| `hermes-native` | native-tui | own-auth | approval-mirror |
| `jcode` | acp-subprocess | own-auth | sse-permission |
| `kimi` | cli-subprocess | session-scoped-config | none |
| `kimi-native` | native-tui | session-scoped-config | hook |
| `kiro-native` | native-tui | own-auth | approval-mirror |
| `open-responses` | sdk-in-process | Xwav provider | none |
| `openai-agents` | sdk-in-process | Xwav provider | none |
| `opencode-native` | native-server | own-auth | sse-permission |
| `pi` | cli-subprocess | Xwav provider | none |
| `pi-native` | native-tui | session-scoped-config | none |
| `qwen` | acp-subprocess | own-auth | sse-permission |
| `qwen-native` | native-tui | own-auth | approval-mirror |

## Install and version contracts

These are the app's supported bounds from
`omnigent/onboarding/harness_install.py`; they are not latest-release claims.
Installer URLs are reviewable metadata, not commands executed by this audit.
Vendor shell installers require separate review before use. Local npm prefixes
can isolate the npm-based CLIs without replacing system tools.

| Install key | Binary | Package or vendor installer | Supported version |
| --- | --- | --- | --- |
| `anthropic` | `claude` | `curl -fsSL https://claude.ai/install.sh | bash` | >=2.1.161 |
| `openai` | `codex` | `@openai/codex` | >=0.137.0 |
| `pi` | `pi` | `@earendil-works/pi-coding-agent` | >=0.84.2 |
| `opencode` | `opencode` | `opencode-ai@~1.18.0` | >=1.17.7, <1.19.0 |
| `qwen` | `qwen` | `@qwen-code/qwen-code` | >=0.18.1 |
| `cursor` | `cursor-agent` | `curl https://cursor.com/install -fsS | bash` | >=2026.06.02 |
| `kimi` | `kimi` | `curl -fsSL https://code.kimi.com/kimi-code/install.sh | bash` | >=0.7.0 |
| `kiro` | `kiro-cli` | `curl -fsSL https://cli.kiro.dev/install | bash` | >=2.10.0 |
| `gemini` | `agy` | `curl -fsSL https://antigravity.google/cli/install.sh | bash` | >=1.1.13 |
| `goose` | `goose` | `brew install block-goose-cli` | >=1.38.0 |
| `hermes` | `hermes` | `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash` | >=0.17.0 |
| `devin` | `devin` | `curl -fsSL https://cli.devin.ai/install.sh | bash` | No declared floor |
| `grok` | `grok` | `curl -fsSL https://x.ai/cli/install.sh | bash` | No declared floor |
| `jcode` | `jcode` | `curl -fsSL https://jcode.sh/install | bash` | No declared floor |

Official npm metadata was queried during this audit: `@openai/codex` 0.163.0
(Node >=16), `@earendil-works/pi-coding-agent` 1.4.0 (Node >=22.19.0),
`@qwen-code/qwen-code` 0.26.0 (Node >=22), and latest supported OpenCode 1.18.x
was 1.18.35. OpenCode 1.19+ is intentionally rejected until its API is validated.
Codex's optional smart-routing hook requires >=0.145 in addition to its general
launch floor. Resolve and pin actual installed versions before claiming success.

Official package metadata:
[Codex](https://www.npmjs.com/package/@openai/codex),
[Pi](https://www.npmjs.com/package/@earendil-works/pi-coding-agent),
[Qwen Code](https://www.npmjs.com/package/@qwen-code/qwen-code),
[OpenCode](https://www.npmjs.com/package/opencode-ai).

## Authentication and external prerequisites

| Family or harness | Required setup beyond installation |
| --- | --- |
| Claude native | `claude auth login --claudeai`, or a compatible Xwav Anthropic provider; `claude auth status` confirms CLI auth. Managed gateway and native Bedrock routes have separate scoped configuration. |
| Codex / Codex native | `codex login`, or a compatible OpenAI provider; CLI status is `codex login status`. CLI config providers and managed gateway routes remain scoped to compatible adapters. |
| Pi / Pi native | A usable selected Xwav provider/model; native Pi uses session-scoped credentials and model configuration. It must not silently fall back to a paid unrelated account. |
| Claude SDK / OpenAI Agents / Open Responses | Compatible provider endpoint, model and locally resolvable credential; a native CLI subscription is not automatically an SDK API key. |
| Antigravity SDK | Optional `google-antigravity` extra and its supported credential path. This is distinct from both the `agy` native CLI and the Harness² workflow. |
| Antigravity native | `agy` with first-run browser sign-in or supported `GEMINI_API_KEY`; stored/API credentials are checked separately from binary availability. |
| Cursor SDK | Optional `cursor-sdk` extra and `CURSOR_API_KEY`; native Cursor browser login is not interchangeable with the SDK key. |
| Cursor native | `cursor-agent login`, checked with `cursor-agent status --format json`. |
| Copilot | Optional `github-copilot-sdk` extra and a GitHub token with Copilot access; supported env variables are COPILOT_GITHUB_TOKEN, GH_TOKEN, GITHUB_TOKEN, or a usable `gh auth` session. Mere token presence cannot prove account entitlement. |
| Qwen / Qwen native | Existing provider configuration or Qwen's interactive `/auth`; no fabricated `qwen login` / `qwen auth status` command. |
| Kimi / Kimi native | The `kimi-code` CLI, with `kimi login` credentials or configured API key. Do not install an unrelated similarly named `kimi-cli` package. |
| OpenCode native | Existing compatible provider config, Bedrock profile, or stored vendor auth. Binary presence alone is not evidence of a usable account. |
| Goose / Goose native | Existing `goose configure` provider/keyring configuration. |
| Hermes / Hermes native | Existing Hermes setup/model configuration and vendor credentials. |
| Kiro native | Existing `kiro-cli` login/profile; readiness currently checks installation/version, not subscription entitlement. |
| Devin native | Existing `devin auth login`; `devin auth status` is available, but native launch readiness is primarily installation-based. |
| Grok | `grok login --device-auth` persisted OAuth is supported by the built-in ACP row. The built-in row explicitly allowlists XAI_API_KEY; all other ambient credentials remain filtered. |
| Jcode | Existing `~/.jcode/config.toml`, or its explicit session-scoped Xwav gateway configuration. The ACP row intentionally does not advertise session-scoped MCP because Jcode ignores that field. |
| Generic ACP | At least one configured `acp:<slug>` agent and its actual CLI, auth and declared environment passthrough. The base `acp` identity alone does not choose an executable. |

The Python environment must include the selected optional SDK extra. In
`pyproject.toml`, Antigravity's protobuf >=7 requirement conflicts with some
optional sandbox/lint dependency groups; use supported separate environments
rather than forcing incompatible packages into one environment.

## Readiness boundaries and audit findings

`omnigent/onboarding/harness_readiness.py` distinguishes a launch gate from the
picker's warnings. SDK launch gates fail open for spec-scoped credentials that
the host cannot observe. Picker readiness checks locally available providers and
credential references. This distinction is intentional; a launchable adapter is
not necessarily authenticated. Unknown community contributions also fail open
when no install metadata is supplied.

Known limits to keep visible:

- Cursor and Antigravity SDK readiness does not import/check the optional SDK;
  a configured credential with a missing extra can still fail on first turn.
- Several own-auth native/ACP rows report binary/version readiness without a
  complete auth probe. A green installation check is not an account entitlement
  check. Do not change account credentials just to make the indicator green.
- Fixed during this audit: Grok advertised XAI_API_KEY but the ACP child did
  not inherit it. The row now allowlists exactly XAI_API_KEY, with default-deny
  behavior retained for other credentials and other ACP rows. The official
  [Grok authentication guide](https://docs.x.ai/build/overview) confirms API-key
  authentication. Jcode retains its separate scoped gateway injection path.
- The native environment requires tmux/PTY and vendor-specific OS support.
  Installing a CLI does not prove the terminal bridge is available.

## Verification

Run hermetic install/readiness/catalog tests with the environment used for the
app. No provider credential or paid model call is needed:

```bash
.venv/bin/python -m pytest tests/onboarding/test_harness_install.py \
  tests/onboarding/test_harness_readiness.py tests/test_harness_readiness.py \
  tests/test_acp_cli_harnesses.py tests/test_harness_plugins.py \
  tests/test_harness_capabilities.py --reruns 0
```

For a human account check, open Settings > Harnesses, select the desired
harness, verify the selected executable/version, complete that vendor's own
login if required, then launch it in a disposable workspace. Confirm the
expected model/provider, approval behavior, interruption and a short response.
A live response can incur provider charges. Live account checks are recorded
separately from this contract test batch. Treat each missing binary, auth step, entitlement, SDK extra or native
terminal prerequisite as a distinct blocker instead of marking every harness
working from one successful mock test.

Audit execution results (mock contracts, no live model calls):

- SDK/headless adapter/executor batch: 1,520 passed, 4 skipped, 18 subtests passed.
- Native adapter/executor batch: 454 passed.
- Open Responses adapter: 28 passed.
- Install/readiness/registry/capability baseline: 297 passed. Two missing-binary
  tests were made hermetic after installed Pi/Kiro executables exposed PATH
  leakage. The combined Harness², readiness, ACP and native catalog suite then
  passed all 62 tests.

These results validate local adapter behavior and protocol contracts, not vendor
credentials, subscription entitlement, or real model output.

## Additional project-local CLI installations

The audit installed additional official Linux x86_64 CLIs under the ignored
`.omnigent/harness-tools` directory. No shell profile, global binary, vendor
account or existing global installation was replaced. Real version-only checks
passed for:

| CLI | Installed version | Installation |
| --- | --- | --- |
| Cursor Agent | 2026.10.19-6bbf2c4 | Official downloads.cursor.com archive; local SHA-256 receipt retained. |
| Devin | 3000.11.92 | Official static.devin.ai manifest/archive; published SHA-256 verified. |
| Kiro CLI | 2.33.1 | Official prod.download.cli.kiro.dev headless archive; published SHA-256 verified. |
| Goose | 1.55.0 | Official aaif-goose/goose GitHub release; published SHA-256 verified. |
| Jcode | 0.99.0 | Official 1jehuang/jcode GitHub release; published SHA-256 verified. |
| Grok | 1.0.67 | Official @xai-official/grok npm package, isolated vendor-npm prefix. |
| Kimi Code | 2.3.0 | Official @moonshot-ai/kimi-code npm package, isolated vendor-npm prefix. |
| Hermes Agent | 0.19.1 (2026.7.30) | Official tag v2026.7.30, pinned commit d25e2dbdbc40b49808c0a0e9cfed21cc90cffab3, isolated Python 3.12 venv. |

Their executable links are under `.omnigent/harness-tools/bin`. Preserve the
adjacent vendor directories: Cursor and Jcode launchers resolve supporting
files relative to their real path; moving only the launcher breaks them. Kiro's
companion `kiro-cli-chat` is linked alongside its main executable. npm integrity
receipts are retained in the isolated prefix lockfile; archive receipts are in
`vendors/<name>/receipt.json`. Version checks stripped credential environment
variables and used temporary vendor/XDG directories; no live model turns ran.

Hermes uses the supported 0.19.1 release that the native bridge documents as
verified. Its official Git tag is `v2026.7.30` (there is no `v0.19.1` tag).
The pinned source was installed editable into an isolated Python 3.12 environment
under `vendors/hermes/venv`; both `hermes --version` and `hermes --help` passed.
The source tree and venv must remain together. This avoids latest stable 0.22.4's
Python 3.14/PM app bootstrap without bypassing the adapter's supported version
floor. No vendor shell installer or global package setup was executed.

Installer inspection also identified why direct archive/package installation
was used: Cursor writes HOME-based paths, Kimi's installer can rename legacy
shims found on PATH, and Jcode's installer writes HOME-based builds and install
telemetry. A custom bin prefix alone would not isolate those scripts.

## Local account validation

Pi 1.4.0, Claude 2.1.283, Qwen 0.26.0, OpenCode 1.18.35 and
Antigravity 1.2.4 were also installed locally; tmux 3.4 and fd supply terminal
and file-discovery prerequisites. Harness² is the primary checkout workflow (`just` / `just benchmark`).
Pi remains the separate chat default; existing user/project harness choices
remain respected. Missing-command aliases in the user's local
bin directory point to these isolated installations.

A bounded direct Codex CLI canary returned `XWAV_CODEX_CANARY_OK` using the
existing account, with no tools. This confirms that CLI account works; it does
not substitute for an end-to-end Xwav transport test. Real Pi process tests
passed 8 cases with 3 skipped, and native terminal tests passed 12 cases.
Pi's separate OpenAI authorization remains pending: browser login returned
`invalid_grant`, and the first device flow timed out without saving credentials.
No Codex credential was copied to Pi. Other vendor account entitlements remain
unverified and require their own login or compatible provider configuration.

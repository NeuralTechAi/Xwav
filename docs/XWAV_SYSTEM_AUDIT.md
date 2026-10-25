# Xwav system audit — 23 October 2026

The reported `input[0]: unknown input item type: additional_tools` failure was
traced to the model-provider boundary, rather than the composer. The affected
Docker job selected `gpt-5.6-sol` against `http://localhost:11434/v1`. That Ollama
installation contains only `nomic-embed-text:latest`, an embedding model. The
sandbox had no Codex login, so ambient detection advertised Ollama solely
because its port accepted connections. The endpoint rejected the Codex request
before an assistant response could start.

## Findings and changes

| Severity | Finding | Resolution / evidence |
| --- | --- | --- |
| High | Embedding-only Ollama was advertised as a chat provider. | Ambient detection now checks installed model capabilities through bounded loopback HTTP requests. Empty, malformed, unreachable and embedding-only services do not qualify. The actual local service now returns false for chat readiness. |
| High | Isolated jobs lacked the user's intended OpenAI account. | Added explicit `sandbox.docker.inherit_codex_login`, disabled by default. Following explicit user approval, enabled it for this trusted local deployment. Each job receives a private copy through stdin, with atomic replacement and mode 0600; no host directory is mounted. A failed copy removes the newly provisioned container. |
| High | Workspace-owned tmux wrapper failed through its executable symlink. | Resolved the real script path before deriving bundled library/binary locations. `tmux -V` now reports 3.4. The three real Codex provider-resume tests initially failed at terminal startup and all passed after this repair. The local wrapper is under the ignored harness-tools directory. |
| Medium | Existing failed job retained its old provider runtime. | Installed the approved login, gracefully restarted only that sandbox's host, and restored its terminal. A settings-only native session check reports `model_provider: openai`, `model: gpt-5.6-sol`, and no error. Its workspace and native thread were preserved. No test prompt was sent to the user's conversation. |

The running server was restarted with its existing database and configuration.
The managed host image was rebuilt with corrected provider detection. Account
inheritance is an administrator setting: every job in this local deployment can
use the server operator's account. It remains inappropriate for untrusted users;
other deployments retain the default of separate sandbox authentication.

Codex's Responses Lite framing explains the unusual input item; upstream records
the `additional_tools` shape in
[OpenAI Codex issue 31894](https://github.com/openai/codex/issues/31894).
The local endpoint/model mismatch was independently established from runtime
configuration, the local model catalog, and the failed session logs.

## Verification

These are scoped suites, not an exhaustive run of the entire repository. Some
regression groups overlap; their counts should not be added as unique tests.

| Area | Result |
| --- | --- |
| Provider detection/adoption, managed hosts, Docker, session resources, preview runtime, skill CLI and ACP catalog | 871 passed |
| Codex executor/provider/home staging and Docker authentication | 218 passed; 4 Windows-only tests skipped; 11 subtests passed |
| Harness² status/demo CLI, skills, Goal APIs, workflow routing and harness readiness/overrides | 143 passed |
| Composer, sidebar, workbench, default preferences and preview components/hooks | 863 passed |
| Harness/credential controls, Goal/Plan components and Git provider controls | 196 passed |
| Final capability detection and authentication regression recheck | 100 passed |
| Real Codex/tmux provider selection, restart and history preservation against isolated mock endpoints | 3 passed |
| Real server/runner Chromium workbench journeys | 10 passed |
| Live OpenAI/Codex account in disposable Docker job | Passed, including explicit `gpt-5.6-sol` from the failed job; expected `XWAV_OK` response received |
| Two disposable jobs from rebuilt image, concurrent checks | Passed; separate marker files, private credential permissions, Codex detected and embedding-only Ollama absent |
| Repository lint, formatting and Python type checks for changed code | Passed |

Browser journeys cover desktop/mobile, light/dark, drafts, navigation,
notifications/scheduler links, preferences, harness controls, separate preview
tabs, viewport interactions, layout, reload, minimize/maximize/close, live source
updates, background updates and updates after the main tab closes. They used an
isolated verification environment, not test messages in the user's project.

## Limits and remaining prerequisites

- A working CLI installation or passing adapter test does not establish a live
  authenticated turn for every external harness. This audit's live provider
  check covers OpenAI/Codex; other vendor accounts still require their own
  credentials and live acceptance checks.
- Harness² is a benchmark optimization workflow. Its demo/status paths pass; it
  is not an interactive chat harness, and arbitrary user benchmarks or cloud
  credentials were not exercised.
- Android/iOS previews are responsive browser viewports with device frames.
  Native APK/IPA execution, Safari-specific behavior and remote-runtime preview
  port publication require separate runtimes/transport.
- The browser suite covers the changed workbench journeys. It does not certify
  every application route, native platform, external integration, workload or
  long-duration performance scenario.

## Manual verification

1. Refresh Xwav at `http://127.0.0.1:6767`, reopen the failed job and resend your
   intended message. The historical failed turn remains in its transcript.
2. Start a new trusted local project job with Codex selected. Confirm it responds
   and can work in that job's own workspace.
3. Open Preview, interact with the app and edit its source. Check that all three
   viewports update while the main tab is open or closed.
4. Open a second project job and confirm its files and changes remain separate.

Disable shared account setup by setting `sandbox.docker.inherit_codex_login` to
false and restarting the server. Existing jobs retain their private login until
it is removed or the container is deleted; the setting controls provisioning.

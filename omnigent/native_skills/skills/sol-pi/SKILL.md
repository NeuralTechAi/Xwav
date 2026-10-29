---
name: sol-pi
description: Assess whether to use a scoped SoL-Pi worker when investigations repeatedly reuse large logs, test output or file observations over several turns. Select automatically when that work benefits from exact paged recall, or when explicitly requested. Skip short tasks, single reads and unrelated coding work.
license: MIT
disable-model-invocation: false
---

# Shared SoL-Pi worker

Any Xwav harness with shell access can call the shared worker. Parents with Xwav
sub-agent tools can attach the exported agent instead. SoL-Pi itself uses Pi's
extension APIs; it is not loaded into Claude, Codex or other vendor processes.
The parent keeps its own harness, account and conversation.

Inspect without starting processes, installing packages or reading credentials:

```bash
xwav sol-pi status --json
```

## Automatic selection and dispatch

The user does not need to mention SoL-Pi or type a slash command. Assess the
request and actual tool traffic. Good candidates are bounded investigations
that repeatedly revisit substantial diagnostic logs, large test results or
repository observations over several model turns. ObservationPack acts on text
results larger than 10 KiB after their first two provider requests. Use that
behavior to judge relevance; a large file or a matching word alone is not enough.

Choose the smallest useful subtask. Keep single reads, short answers, small edits
and already concise work on the current harness. Do not generate extra output or
unnecessary turns to justify using a worker. Respect user instructions such as
"do it here", "do not delegate", manual-only skill settings and disabled skills.

Once selected, announce the scoped delegation briefly and check readiness using
the offline status command. Prefer an attached SoL-Pi child through Xwav's normal
sub-agent tools, preserving the parent-session policy/inheritance path. Use the
CLI only when its separate-session policy boundary is permitted for the job.
Dispatch automatically within the user's task and existing model-use budget
when the worker, account and appropriate tools are already configured. Do not
change the main harness or automatically create/import a persistent agent.

If no suitable worker, credentials, policy path or budget is available, continue
with the current harness and explain the limitation briefly when relevant.
Do not run a paid authentication probe, retry failed logins in a loop, install
packages, copy credentials or expand the task just to enable automatic dispatch.

For a suitable scoped task or an explicit request, write a task file and invoke:

```bash
xwav sol-pi run --project /path/to/project --task-file /path/to/task.md --timeout 600 --max-iterations 20
```

The caller may choose `--model` from that job's configured Pi models. The worker
uses Xwav's normal Pi executor and tools. Node >=22.19, compatible Pi and its
model account must be available in that job. Report missing prerequisites;
do not copy host logins or install hooks, plugins, global settings or another
runtime without the user's authorization. A Docker job has its own environment.

Keep the task small. Include only needed context in the task file. Do not scrape
or transfer a parent transcript automatically, run recursively or delegate work
outside the user's scope. Wait for the worker, review its diff and checks, then
report its result. Main worker model calls still cost tokens; no cost reduction
is guaranteed.

For a persistent child agent, export into a new directory:

```bash
xwav sol-pi export-agent /path/to/parent-agent/agents/sol-pi --project /path/to/project
```

Add `sol-pi` to the parent's `tools.agents` list. Use its normal sub-agent tools
so the existing parent-session policy/inheritance path applies. Alternatively,
archive the exported directory contents as a `.tar.gz` and import it in Settings
→ Skills, tools & plugins. Existing agent directories are never overwritten.

## Lightweight profile

Only ObservationPack is enabled: large repeated observations become local handles
with exact paged recall. Action Fusion is off because this worker keeps Xwav's
bridged edit and shell tools. Remote log reduction and automatic compaction are
also off. Their pinned source is retained, but Xwav does not silently enable
additional model calls or automatic continuation. Existing Pi auth, defaults,
project files and global configuration are unchanged. Avoid attaching a second
SoL-Pi extension to the same worker.

Source: NVlabs/SoL-Pi, MIT, pinned in `upstream.json`. The supporting TypeScript
source is read only by the optional worker, not during native skill discovery.

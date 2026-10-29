# SoL-Pi for every Xwav harness

Xwav exposes NVIDIA's [SoL-Pi](https://github.com/NVlabs/SoL-Pi) as a shared,
optional worker. Claude, Codex, Pi and other parent harnesses can call the same
CLI using their shell tools, or attach the exported agent through Xwav's existing
sub-agent tools. Their own primary harness and default remain unchanged.
The upstream extension executes inside Pi, whose public APIs it requires.
This does not patch other vendor runtimes or their internal context managers.

## Lightweight and on demand

The integration bundles roughly 130 KB of unmodified TypeScript source, pinned
to `219568034fa54ed121ede80961655e33dfb9d0e3` (SoL-Pi 0.1.1, MIT). Its manifest
records exact source hashes. No npm dependencies, hooks, extra MCP servers,
telemetry process, background worker or model requests are added to Xwav startup
or skill discovery. The source loads only when the worker starts.

The worker enables **ObservationPack**: repeated large tool results become small
handles, with their original text retained for paged recall. This still uses the
worker's normal main model and can incur normal model charges. There is no
guaranteed cost saving or claim that parent-model context is compressed.

Action Fusion remains off because the worker uses Xwav's bridged edit/shell tools
and their existing approval path. Evidence-Preserving Reducer and Online Context
Compact remain off: no extra log-reduction model calls or automatic continuation.
The supported source is included without silently enabling those features.
Existing project/global Pi settings and credentials are not rewritten or copied.

## From any caller harness

In a supported job, `/sol-pi` loads the portable skill on demand. Harnesses with
their own unbridged skill catalogs can still call the CLI from their shell:

```bash
xwav sol-pi status --json
xwav skills show sol-pi
xwav sol-pi run --project /path/to/project --task-file /path/to/task.md --timeout 600 --max-iterations 20
```

### Automatic use

The shared skill selector also considers SoL-Pi without a slash command. Its
metadata targets bounded investigations that repeatedly reuse large observations
over several model turns. Once selected, its instructions guide a readiness,
policy and budget check before automatically dispatching an already configured
worker. Short tasks, a single large read and generic coding work stay on the
current harness. Explicit user opt-outs and manual-only/disabled skills win.

This is an agent decision based on the actual task and tool traffic, not a
keyword trigger or a background classifier. No model request runs merely to
decide whether to use SoL-Pi. Selection loads only the skill instructions, not
the TypeScript runtime. It never silently installs a runtime, creates a reusable
agent or acquires an account. If readiness or the permitted policy/budget path
is missing, the agent continues normally. Normal worker usage can still cost
model tokens; automatic selection is not a guarantee of savings.

The task file contains the specific request and only the necessary context.
The adapter does not scrape a parent transcript. It invokes Xwav's normal Pi
executor rather than running the raw upstream hand-off script. `--model` can
select a model already configured for that job's Pi account. Node >=22.19 and a
compatible Pi runtime are required at execution time. Upstream tests Pi 0.84.2,
1.0.4 and 1.3.0; Xwav additionally checks the lightweight profile on its local
Pi 1.4.0 acceptance runtime. Missing runtime/auth is a setup requirement, not
permission to copy a host account into a job. Containers have their own setup.

Direct runs are separate Xwav sessions in the same project/job environment.
They use normal Xwav tools and their own session's policies. Custom caller
session policies are not copied by the CLI. Use an attached child agent for
the existing parent-session policy/inheritance path. Run inside the intended
job sandbox and scope tasks to it. Do not start concurrent writers against the
same files. A timeout/iteration limit bounds the task but is not a currency cap.

## Reusable worker through shared agent tools

Export into a **new** parent-agent directory:

```bash
xwav sol-pi export-agent /path/to/parent/agents/sol-pi --project /path/to/project
```

Add `sol-pi` to the parent's `tools.agents` list. Any parent harness that exposes
Xwav's agent tools can then dispatch it with the usual named child-agent tools.
This reuses Xwav's task status, cancellation, session tree and policy inheritance.
The exported bundle has its own extension entry point and needs no global Pi
installation changes. It is a worker configuration, not another native skill.
The catalog still contains exactly one `sol-pi` skill, with normal project/user
name and content deduplication.

Alternatively, make a `.tar.gz` of the exported directory's **contents**
(`config.yaml` at archive root) and import it through **Settings → Skills, tools
& plugins**. The standard ownership, validation and tool allowlist apply.
The exported workspace is explicit; update it before moving to another machine.
Do not attach another SoL-Pi runtime to the same worker. Remove an exported agent
with the normal agent-management flow when it is no longer needed.

Observation archives stay under the worker's Pi session storage and can contain
tool output. They follow that session's access and retention policy; no automatic
archival cleanup is introduced. Never send a restricted log to a remote reducer
merely to save tokens.

## Verify

Run `xwav sol-pi status --json`: expect `verified: true`, ObservationPack true,
and the other three features false. Export an agent and confirm the destination
contains the pinned runtime and exactly one extension entry. A second export to
the same path must refuse without replacing it.

From your configured harness, request a scoped SoL-Pi task, such as reading a
large local diagnostic log and quoting the relevant lines. The worker should
return its findings and exact checks. Check that your original harness/default
and `.pi/settings.json` remain unchanged. Check normal usage costs separately.

To check automatic selection, start a new job with an attached worker and ask
it to investigate recurring failures across large diagnostic outputs, quoting
the relevant evidence. Do not name SoL-Pi. Inspect the skill/tool events: an
appropriate delegation should load its guidance first, announce a bounded task
and then dispatch the worker. Follow with a short factual question: it should
answer directly. Repeat the investigation with "do not delegate" and confirm
it remains on the current harness. A missing account should result in normal
local work rather than setup attempts. Model relevance judgments can vary.

Automated coverage extends native catalog/filter/duplicate and Claude/Codex
resource-launch tests, adapter lifecycle and command forwarding, and an offline
Pi acceptance probe. No live model efficiency benchmark or cost comparison is
implied by those checks.

Automatic-routing validation: 149 prompt, adapter, catalog, override, Pi and
skill-loader checks passed. These verify the guidance and loading/dispatch
contracts, including real offline observation recall. They do not benchmark
semantic routing decisions or savings across live model providers.

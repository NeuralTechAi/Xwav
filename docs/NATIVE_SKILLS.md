# Xwav native skills

Xwav ships 37 offline skill resources. The normal skill discovery and loading paths expose them as defaults, after agent, project, and user skills. Native defaults are suppressed when their canonical name, plugin alias, or normalized instruction content already exists. Existing user and project skills are preserved. `skills: none` disables defaults; an explicit skill list selects only those defaults. No global agent configuration is rewritten.

Inspect the installed catalog without network access or external tools:

```bash
xwav skills list
xwav skills list --json
xwav skills show context7-mcp
```

In a supported session, type `/` in the composer to discover skills, or invoke a named skill such as `/unslop`. Shared SDK skill loading, Claude SDK/native overlays, and Codex skill sources load the packaged resources. Pi RPC and native TUI sessions on Pi 1.4.0 or later load defaults through its supported `resources_discover` extension event after Pi has loaded user, project, and package skills. Existing names and normalized instruction content suppress matching defaults. `skills: none` disables them; named lists load only selected defaults. Older Pi versions keep their existing catalog. Other vendor-native shells retain their own catalogs. The web composer conservatively omits pre-launch Pi defaults because it cannot enumerate the vendor's full package catalog; Pi's own `/skill:name` commands and RPC `get_commands` report the resources actually loaded. No global resources are copied.

## Included sources

| Source | Included | Runtime setup |
| --- | --- | --- |
| [Addy Osmani agent-skills](https://github.com/addyosmani/agent-skills) | 25 engineering skills | Offline instructions and supporting resources |
| [Andrej Karpathy skills](https://github.com/multica-ai/andrej-karpathy-skills) | `karpathy-guidelines` | Offline coding guidelines; no plugin or tool installation |
| [Michael Shimeles skills](https://github.com/michaelshimeles/skills) | `greploop`, `greploop-apps`, `unslop` | Review workflows need their documented review tools |
| [Context7](https://github.com/upstash/context7) | `context7-mcp` | Node/npx; API key optional, public limits apply |
| [21st.dev Magic MCP](https://github.com/21st-dev/magic-mcp) | `21st-ui` | Hosted 21st MCP; `API_KEY_21ST` required |
| [Strix](https://github.com/usestrix/strix) | `penetration-testing-with-strix` | Optional Strix CLI, Docker and model credentials for local scans; explicit authorized scope and budget |
| [REA](https://github.com/morluto/rea) | `reverse-engineer-anything` | Node/npx; optional platform tools depend on the artifact |
| [Graphify](https://github.com/Graphify-Labs/graphify) | `graphify` | uv/uvx; deterministic code graph works without a model key |
| Xwav GitHub operations | `github-ops` | Existing GitHub connection / PR panel and authenticated `gh`; complements native Git workflow guidance |
| [Harness²](https://github.com/google-research/harness2) | `harness2` | Optional pinned Python runtime; standalone benchmark optimizer, credential-free local demo |

External source revisions, licenses, adaptations and omissions are recorded in `omnigent/native_skills/sources.json` and `integrations.json`; original Xwav resources are marked first-party. Each skill carries its applicable license. Michael's `code-structure`, `new-feature` and `evidence-driven-testing` lack redistribution licenses at the reviewed revision; `before-and-after` has a restrictive PolyForm Shield license. Those four are omitted. Upstream global AGENTS instructions, hooks, and installers are not installed.

## Optional MCP tools

A skill is instruction content; its optional MCP server or CLI is a separate runtime dependency. Discovery does not start these processes, upload repositories, make paid requests, or begin security scans.

For Context7, 21st, REA or Graphify, export the reviewed preset into an agent's spec directory, then launch that agent:

```bash
mkdir -p my-agent/tools/mcp
xwav skills mcp-config context7-mcp > my-agent/tools/mcp/context7.yaml
```

The other preset names are `21st-ui`, `reverse-engineer-anything` and `graphify`. Read each skill's setup first. Keep credentials in the runner environment, never in committed YAML. Graphify's MCP preset reads `graphify-out/graph.json`; build that graph in the intended workspace first. Strix has no MCP preset and remains an explicit CLI workflow.

## Validation

The integration tests cover packaged resources, provenance, filters, duplicate overrides, session resolution, Claude/Codex launch resources, Pi 1.4 RPC/native launch arguments and real offline command discovery with user overrides, MCP config parsing and a mocked credentialed handshake. Real protocol smoke checks initialized Context7 and REA and listed tools without invoking them. Graphify built a tiny local fixture graph without a model key. Live 21st generation, Strix scans and platform-specific REA tools require their own credentials/dependencies and were not executed.

To verify manually, run `xwav skills list`, select a supported host and harness, type `/unslop`, and inspect the loaded instructions. Add a project skill with the same name and confirm its instructions win. Try `skills: none` in an agent spec and confirm native defaults disappear from that session's skill menu.


## Harness² benchmark optimization

Read the [Harness² integration guide](HARNESS2.md) or run `xwav skills show harness2`. `xwav harness2 status` checks the optional runtime, and `xwav harness2 demo --output /tmp/xwav-harness2-demo --k 2 --mode both` runs deterministic local recursion. The optional `harness2` dependency extra pins the reviewed source revision. This integration is a native CLI workflow, not a selectable interactive chat executor. Real benchmarks need separate setup, credentials and independent isolation; the upstream Codex substrate bypasses its own sandbox and approval checks. Xwav's guardrails are unchanged.

## Git and GitHub

`git-workflow-and-versioning` already covers local branches, commits, conflicts, worktrees and releases. `github-ops` adds GitHub issues, PRs, reviews, checks and Actions through the existing connection/PR panel and `gh` CLI. No duplicate GitHub MCP server or agent is installed. The latter is original Xwav guidance under Apache-2.0, recorded as first-party provenance rather than an upstream revision. Try `xwav skills show github-ops` or `/github-ops` in a supported session.

Quality Lab preparation is available as `/preproduction-tests`. It documents supported test scripts and `.xwav/preproduction.json`, reuses project suites, and distinguishes responsive browser tests from native device tests.

## User integrations in Settings

Open **Settings → Skills, tools & plugins**. Create a reusable agent to attach
portable `SKILL.md` files and configure HTTP or stdio MCP tools. Choose that agent
in **New Job**, then type `/` to select its skills. Reattaching a skill name replaces
the draft attachment; bundled skills override host skills with that name.

For supporting files or scripts, import a complete Xwav agent `.tar.gz` from the
same page. Use `config.yaml` plus `skills/<name>/SKILL.md` and supporting files.
An import with an existing owned agent name updates it rather than making a copy.
The existing server validator and tool allowlist apply to every import.

Harness-native plugins retain their original install and execution rules. Inspect
installed integrations under **Harnesses → selected harness → Skills / MCP servers /
Plugins**. Install them using the harness's own flow in the environment that runs
it. A local host plugin is not automatically present in a Docker job. Portable
agent skills and MCP declarations travel with the agent; stdio dependencies still
need installation inside that job. Server UI plugins remain administrator-managed.

## Karpathy guidelines

Invoke `/karpathy-guidelines` in a supported Xwav job, or inspect the instructions
with `xwav skills show karpathy-guidelines`. The canonical upstream skill is
bundled once, unchanged, at revision `2c606141936f1eeef17fa3043a72095b4765b9c2`. Its four principles
remain one skill rather than four additional entries that overlap engineering
skills already bundled. Upstream CLAUDE.md, Cursor rules and plugin installers
are not installed. User/project skills and plugin copies suppress the native
default by canonical name, namespaced alias or normalized instruction content.

The upstream skill, README and plugin manifest declare MIT but supply no standalone
LICENSE at this revision. `LICENSE.upstream.json` preserves the original manifest,
including its license and author; the source revision and content checksum are
recorded in `integrations.json`.

To refresh an existing local Docker host image with this catalog without
reinstalling harnesses or browser tools:

```bash
docker build -f deploy/docker/Dockerfile.native-skills -t xwav-host:local .
```

New Docker jobs use the refreshed image. Already-running sandboxes keep their
installed resources until recreated.

## Automatic skill selection

Users can describe a task in ordinary language; slash commands are optional.
Xwav's shared runtime tells the agent to match the request against its available
skill names and descriptions, load the full instructions for the smallest relevant
set, and briefly identify the skills it uses. Native harnesses use their own loaded
skill catalogs and loaders; the shared loader exposes descriptions for bundled,
host and native skills, not just their names. No separate routing service or extra
model call is needed.

Selection respects the job's skill filters and user/project overrides. It does not
load every skill, force a skill for unrelated or trivial requests, install tools,
or grant permission for external actions. Missing dependencies still need setup.
The model makes the relevance decision; a manual skill selection remains available
when the user wants a specific workflow. For example, ask “Investigate why this
calculator returns incorrect results” or “Review this change for security issues”
without typing a slash command.

For an existing local Docker image, deploy this runtime update with
`docker build -f deploy/docker/Dockerfile.skill-selection -t xwav-host:local .`.
Start a new job to pick up the updated runtime. Running sandboxes retain the
Python modules loaded by their existing runner processes.

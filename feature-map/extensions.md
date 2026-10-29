# Skills, tools and plugins

Settings → **Skills, tools & plugins** (`/settings/extensions`) is the entry point
for portable skills, MCP tools, reusable agents and harness plugin inventories.
Custom agent management is enabled by default when the server supports user
agents. Operators can explicitly disable `custom_agents_settings_ui`.

## Verify

Use the isolated environment from [Verify Xwav](skills/verify-omnigent/SKILL.md).
On desktop and mobile:

- Open the Settings sidebar entry and each integration card. Skills and MCP open
  the agent form; Agents opens management; Harness plugins opens Harnesses.
- Create a uniquely named agent with a configured harness and model. Attach a
  SKILL.md with YAML name and description. Attach the same name again and verify
  only one command remains. Remove it, reattach, save, reload and find the agent.
- Start New Job with the saved agent. Describe a task matching its skill description
  without a slash command; confirm the agent loads and uses the applicable skill.
  Type `/` to select a specific skill explicitly. Bundled
  skills take precedence over host skills with the same name.
- Configure HTTP or stdio MCP servers on the agent. Save, reload and inspect the
  configuration. Stdio executables must exist in the job environment.
- Import a complete .tar.gz agent bundle from the hub. It must contain config.yaml;
  supporting skill files belong in skills/<name>/. A rejected bundle leaves the
  page open with the server's error. Re-importing the same agent name replaces
  that user's saved configuration instead of creating a duplicate.
- In Harnesses, choose an online connected host and a supported ready harness.
  Inspect Skills, MCP servers, tools and plugin details. Plugin support is harness
  specific. Install plugins through that harness's own installation flow on the
  same host/sandbox; start a new job to use them. Host plugins are not automatically
  installed in Docker jobs. Server UI extensions remain administrator-installed.

Maintained browser coverage extends `tests/e2e_ui/sessions/test_custom_agent_edit.py`
with `test_extensions_create_agent_with_portable_skill`, at desktop/mobile sizes.
Component tests cover import failure, catalog refresh, unsupported servers and
file replacement/removal. Agent install tests cover persistence, MCP declarations,
user ownership and same-name replacement. Existing runtime discovery tests cover
native skill/plugin resolution and precedence.

On-demand activation is covered by `tests/runtime/test_prompt.py`,
`tests/tools/builtins/test_load_skill.py` and `tests/spec/test_parser.py`:
initial prompts/tools expose metadata rather than skill bodies, manual-only
skills stay out of automatic catalogs, explicit loading remains available, and
reference contents are read only through a separate requested file read. These
checks verify framework behavior; semantic relevance remains the model's
selection decision, guided by the task rather than keyword triggers.

## Shared SoL-Pi worker

`/sol-pi` provides portable guidance for any caller harness. Inspect it with
`xwav sol-pi status --json`, then export a reusable worker with
`xwav sol-pi export-agent <new-directory> --project <workspace>`. Attach that child
to a parent's `tools.agents` list, or import its archive through the existing
agent form. A caller with shell tools can use `xwav sol-pi run --task-file <file>`.
Opening the skill/status must not start Pi, install dependencies, copy credentials
or change the caller's harness. A run is explicit and uses the job's Pi account.

Automatic selection needs no `/sol-pi` command: a repeated large-log investigation
can select its skill, assess readiness and dispatch a configured, scoped worker.
Short tasks and single reads stay local. User opt-outs, manual-only skills and
disabled catalogs must suppress automatic selection. Missing prerequisites must
not launch setup or login. Agent relevance decisions remain model-dependent.

The worker enables local ObservationPack only. Verify packed large observations
remain recallable and original history remains intact. Existing edit/shell tools
retain their normal behavior. No reducer call or automatic continuation starts.
`tests/cli/test_sol_pi.py` covers adapter/export lifecycle and an offline real-Pi
probe. Existing native skill tests cover Claude/Codex overlays, precedence and
duplicate suppression; no extra MCP server or vendor prompt hook is required.

# Xwav native skills

Xwav ships 33 offline skill resources. The normal skill discovery and loading paths expose them as defaults, after agent, project, and user skills. Native defaults are suppressed when their canonical name, plugin alias, or normalized instruction content already exists. Existing user and project skills are preserved. `skills: none` disables defaults; an explicit skill list selects only those defaults. No global agent configuration is rewritten.

Inspect the installed catalog without network access or external tools:

```bash
xwav skills list
xwav skills list --json
xwav skills show context7-mcp
```

In a supported session, type `/` in the composer to discover skills, or invoke a named skill such as `/unslop`. Shared SDK skill loading, Claude SDK/native overlays, and Codex skill sources load the packaged resources. Pi and other vendor-native shells retain their own catalogs. Their discovery mechanisms cannot reliably enumerate all user skills, so this integration does not inject defaults or advertise commands those shells cannot load without duplication.

## Included sources

| Source | Included | Runtime setup |
| --- | --- | --- |
| [Addy Osmani agent-skills](https://github.com/addyosmani/agent-skills) | 25 engineering skills | Offline instructions and supporting resources |
| [Michael Shimeles skills](https://github.com/michaelshimeles/skills) | `greploop`, `greploop-apps`, `unslop` | Review workflows need their documented review tools |
| [Context7](https://github.com/upstash/context7) | `context7-mcp` | Node/npx; API key optional, public limits apply |
| [21st.dev Magic MCP](https://github.com/21st-dev/magic-mcp) | `21st-ui` | Hosted 21st MCP; `API_KEY_21ST` required |
| [Strix](https://github.com/usestrix/strix) | `penetration-testing-with-strix` | Optional Strix CLI, Docker and model credentials for local scans; explicit authorized scope and budget |
| [REA](https://github.com/morluto/rea) | `reverse-engineer-anything` | Node/npx; optional platform tools depend on the artifact |
| [Graphify](https://github.com/Graphify-Labs/graphify) | `graphify` | uv/uvx; deterministic code graph works without a model key |

Pinned upstream revisions, licenses, adaptations and omissions are recorded in `omnigent/native_skills/sources.json` and `integrations.json`. Each skill carries its upstream license. Michael's `code-structure`, `new-feature` and `evidence-driven-testing` lack redistribution licenses at the reviewed revision; `before-and-after` has a restrictive PolyForm Shield license. Those four are omitted. Upstream global AGENTS instructions, hooks, and installers are not installed.

## Optional MCP tools

A skill is instruction content; its optional MCP server or CLI is a separate runtime dependency. Discovery does not start these processes, upload repositories, make paid requests, or begin security scans.

For Context7, 21st, REA or Graphify, export the reviewed preset into an agent's spec directory, then launch that agent:

```bash
mkdir -p my-agent/tools/mcp
xwav skills mcp-config context7-mcp > my-agent/tools/mcp/context7.yaml
```

The other preset names are `21st-ui`, `reverse-engineer-anything` and `graphify`. Read each skill's setup first. Keep credentials in the runner environment, never in committed YAML. Graphify's MCP preset reads `graphify-out/graph.json`; build that graph in the intended workspace first. Strix has no MCP preset and remains an explicit CLI workflow.

## Validation

The integration tests cover packaged resources, provenance, filters, duplicate overrides, session resolution, Claude/Codex launch resources, MCP config parsing and a mocked credentialed handshake. Real protocol smoke checks initialized Context7 and REA and listed tools without invoking them. Graphify built a tiny local fixture graph without a model key. Live 21st generation, Strix scans and platform-specific REA tools require their own credentials/dependencies and were not executed.

To verify manually, run `xwav skills list`, select a supported host and harness, type `/unslop`, and inspect the loaded instructions. Add a project skill with the same name and confirm its instructions win. Try `skills: none` in an agent spec and confirm native defaults disappear from that session's skill menu.

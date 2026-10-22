---
name: graphify
description: Build and query a local code knowledge graph with Graphify, explain symbols and trace paths between components. Use for repository architecture questions or an explicit graph request.
---

# Graphify in Xwav

This is an adapter for Graphify-Labs/graphify (PyPI package **graphifyy**, double y), reviewed at 0.9.93. The CLI and optional MCP server run outside Xwav; installing this skill alone does not install or connect them. Do not run `graphify install`: Xwav already supplies this skill.

## Local code workflow

Use an existing compatible `graphify` executable, or the isolated version-pinned command `uvx --from graphifyy==0.9.93 graphify`. Python >=3.10 and uv are prerequisites for that form. Do not install globally or change other agents' settings automatically.

1. For an existing `graphify-out/graph.json`, query it directly: `graphify query "question"`, `graphify explain "Symbol"`, or `graphify path "A" "B"`. These commands also accept `--graph /absolute/path/graph.json`.
2. To build or refresh a code-only graph in an authorized local project, run `graphify update /absolute/path/to/project`. It parses code locally and writes graph artifacts under that project's `graphify-out`. Inspect warnings and the generated report before treating graph edges as facts.
3. Use the returned EXTRACTED / INFERRED / AMBIGUOUS labels honestly. Cite source paths and distinguish inferred relations from observed calls.
4. Do not upload documents or start semantic extraction, provider-backed labeling, cloud synchronization, watches or hooks without authorization. Non-code media can need model calls and extra packages; plain code parsing needs no provider key.

Prefix CLI examples above with `uvx --from graphifyy==0.9.93` when no compatible existing CLI is installed.

## Optional MCP access

Export `xwav skills mcp-config graphify` to the agent spec's `tools/mcp/graphify.yaml`. It launches `uvx --from graphifyy[mcp]==0.9.93 graphify-mcp --transport stdio` against `graphify-out/graph.json` relative to the runner's working directory. Build that graph first, or replace the preset graph argument with its absolute path. An absent graph is a prerequisite failure; do not claim that MCP is connected until initialization and tools/list succeed. This local MCP path does not need a paid service or API key.

The skill is adapted from the upstream README and CLI contracts. Upstream license and notices are bundled alongside it.

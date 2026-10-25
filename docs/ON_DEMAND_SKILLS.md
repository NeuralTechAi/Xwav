# On-demand skill activation

Xwav exposes skill names and short descriptions for discovery. Skill bodies are
included in model context when selected or explicitly invoked. Parsing skill
files and comparing content hashes for duplicate discovery is not activation;
it does not execute scripts or inject every body into the prompt.

The shared runtime instructions require the smallest set that materially helps
the current request. A keyword overlap or generic coding request is insufficient.
Unrelated/trivial requests can use no skills. Previously loaded instructions are
reused unless changed, lost from context, or explicitly requested again.
References and scripts are used only when required for the current step.
Automatic semantic relevance remains a model decision, rather than a fixed
keyword rule or a guarantee that every model will select perfectly.

The built-in automatic catalog excludes skills marked with either:

```yaml
# SKILL.md frontmatter
# Keeps explicit invocation and slash-menu visibility.
disable-model-invocation: true
```

```yaml
# agents/openai.yaml, inside the skill folder
policy:
  allow_implicit_invocation: false
```

Either restriction wins. Invalid sidecar policy mappings raise a parsing error
instead of silently enabling automatic use. Manual-only names are also omitted
from automatic loader error suggestions. Explicit invocation remains available;
`user-invocable: false` separately controls visibility in the slash menu. Native
harnesses retain their vendor-specific invocation mechanisms and policies.

## Validation

- 422 parser, loader, reference-reader, prompt, native catalog and Pi tests passed
  (`/tmp/xwav-on-demand-skills-tests.log`).
- 168 additional source-discovery, bundle, Codex and tool-manager checks passed.
  The real Codex marketplace-outage test timed out in its vendor loaded-skill
  query. It also fails using the unchanged parser from HEAD, independently of
  these changes (`/tmp/xwav-skill-discovery-baseline.log`).
- The final 28 loader checks passed after removing manual-only error suggestions
  (`/tmp/xwav-on-demand-loader-final.log`).
- The local `xwav-host:local` image was updated and passed a network-disabled,
  non-root smoke test: runner import, manual-only parsing, metadata-only prompt
  and explicit skill loading (`/tmp/xwav-on-demand-skills-image-smoke.log`).
- Ruff and whitespace checks passed. Existing containers were not restarted.

## Try it

Start a new job so its harness receives a fresh catalog and instructions. Ask a
simple unrelated question, then ask for a task that matches one installed skill.
Inspect skill/read tool events: the first request should not activate skills;
the matching task should load only the relevant skill and any needed references.
Follow up within the same task and confirm it reuses instructions already in
context. Explicitly invoke a manual-only skill to verify it still loads.

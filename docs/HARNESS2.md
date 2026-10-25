# Harness² integration

Xwav exposes the reviewed [Google Research Harness²](https://github.com/google-research/harness2) benchmark optimizer through `xwav harness2` and a native `harness2` skill. Harness² recursively edits and evaluates agent harnesses using OpenCode or Codex. It does not implement an interactive chat protocol, so Xwav does not list it as a chat executor.

The optional runtime is pinned to `1cfe254e8d25b15f37048c3730134686abe60335` (Apache-2.0). It requires Linux and Python 3.12 or 3.13. Install this checkout with its optional `harness2` extra, or install the pinned runtime into Xwav's Python environment:

```bash
uv pip install 'harness2 @ git+https://github.com/google-research/harness2.git@1cfe254e8d25b15f37048c3730134686abe60335'
xwav harness2 status --json
xwav skills show harness2
```

The adapter verifies the installed VCS revision before forwarding a command. It invokes the current Python interpreter directly and preserves upstream output and exit status. It never downloads the runtime, changes agent configuration or starts an experiment during normal chat or skill discovery.

## Primary local workflow

The checkout's default `just` recipe opens Harness² status. Use
`just benchmark <command> ...` or `xwav harness2 <command> ...` for the same
workflow. `just --list` still lists development recipes. This default does not
start a benchmark or change the interactive chat executor.

## Verify without model credentials

```bash
xwav harness2 demo --output /tmp/xwav-harness2-demo --k 2 --mode both
```

Expect two completed tasks, zero failures, and `demo.json` in the output directory. The demo runs the actual recursion, proposal, composition, reflection and persistent-library workflow against deterministic editors and real local Python ledger calculations. It runs both parallel and sequential modes. Repeating the command resumes the recorded tasks; choose a fresh output directory for a clean execution.

## Benchmark commands

| Xwav command | Upstream entrypoint | Effect |
| --- | --- | --- |
| `harness2 status` | Package metadata inspection | Offline installation and reviewed revision check |
| `harness2 demo` | `harness2-demo` | Credential-free deterministic local demo |
| `harness2 check` | `harness2-check` | Offline prerequisites check for an installed benchmark |
| `harness2 run` | `harness2` | Explicit benchmark sweep; model calls unless `--dry-run` |
| `harness2 judge` | `harness2-judge` | Explicit grading; model costs may apply |
| `harness2 report` | `harness2-report` | Report existing results |

Pass `--help` after any forwarded command for upstream options. JobBench, LAB and WorkBuddy benchmarks need their own setup and dependencies. The [pinned setup guide](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/docs/SETUP.md) explains the upstream checkout, third-party patches, model configuration and benchmark installation. The Python extra alone does not install benchmark datasets or executors. Start with `check` and a scoped `run --dry-run`, then use the same benchmark, subset, substrate, budget, mode and seed for run, judge and report. An unconfigured check exits nonzero and explains the missing prerequisites.

Upstream model-backed benchmark executors use unrestricted network access, and its Codex substrate bypasses approval, sandbox and hook-trust checks. These are upstream standalone benchmark semantics. Run such experiments in an independently isolated environment with appropriate network restrictions, an explicit authorized task scope and model budget. Xwav does not disable its own guardrails, automatically run model-backed benchmarks, or automatically adopt optimized scripts or policies into active chat agents.

Deterministic demo tests prove local orchestration and adapter execution. They do not prove real model performance, external benchmark readiness, interactive chat compatibility or the safety of generated benchmark harnesses.


## Web interface

Open Settings → Harnesses → Google Harness², or select the benchmark entry in
the new-session harness menu. The page shows the pinned runtime status on the
Xwav server and commands for installation checks, the local demo, sweeps, and
reports. The Configured filter includes Harness² when that server runtime is
pinned. Runtime status is independent of the selected chat host. Commands run
explicitly in your terminal; copying does not start a benchmark or spend credits.

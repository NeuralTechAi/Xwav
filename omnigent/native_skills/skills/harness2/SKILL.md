---
name: harness2
description: Optimize benchmark agent harnesses with Harness² recursive Propose–Probe–Compose workflows. Use when the user explicitly asks for Harness² recursion, a deterministic local demo, or supported JobBench, LAB or WorkBuddy benchmark experiments.
license: Apache-2.0
---

# Harness² in Xwav

Harness² optimizes the prompts, skills, scripts and orchestration around an agent. It is a standalone benchmark orchestrator with OpenCode and Codex substrates. It is available through `xwav harness2`; it is not an interactive Xwav chat executor or a replacement for Xwav policies.

## Setup and local verification

Requires Linux and Python 3.12 or 3.13. Xwav packages this guidance offline; the upstream runtime is optional. Inspect it without importing the runtime or making model requests:

```bash
xwav harness2 status
xwav harness2 status --json
```

Install the reviewed runtime into the same Python environment as Xwav using the optional `harness2` extra when installing this checkout, or the exact pinned requirement below:

```bash
uv pip install 'harness2 @ git+https://github.com/google-research/harness2.git@1cfe254e8d25b15f37048c3730134686abe60335'
```

Run the real recursion engine with deterministic editors and local Python tasks, without model credentials:

```bash
xwav harness2 demo --output /tmp/xwav-harness2-demo --k 2 --mode both
```

Read `demo.json` under the output directory: expect two tasks completed, zero failed, execution and editor counts greater than zero, and results from both parallel and sequential recursion. Repeating the same command resumes existing results. Use a new output directory to test a clean run.

## Explicit benchmark experiments

The runtime supports JobBench (`jb`), LAB (`lab`) and WorkBuddy (`wb`), and OpenCode (`oc`) or Codex (`cx`) substrates. Benchmark setup, model credentials and runtime dependencies are separate. Follow the pinned upstream [setup guide](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/docs/SETUP.md) and [benchmark guides](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/docs/BENCHMARKS.md). The checkout's third-party runners and patches may be needed for setup; installing the Python package alone does not install benchmarks.

Use the Xwav commands to inspect upstream options and readiness:

```bash
xwav harness2 run --help
xwav harness2 check --bench lab --substrate cx
xwav harness2 run --bench lab --substrate cx --k 1 --mode parallel --max-tasks 1 --dry-run
```

`--dry-run` previews task selection after the benchmark has been set up. It does not substitute for benchmark installation. Start real benchmark runs or judging only when the user has authorized the specific benchmark, task scope and model budget. A real sweep makes multiple executor and editor calls per task; judging may also incur costs. Reports read existing results:

```bash
xwav harness2 run --bench lab --substrate cx --k 1 --mode parallel --max-tasks 1
xwav harness2 judge --bench lab --substrate cx --k 1 --mode parallel
xwav harness2 report --bench lab --substrate cx --k 1 --mode parallel
```

Keep benchmark, subset, substrate, recursion budget, mode and seed aligned across run, judge and report. Use a dedicated `HARNESS2_RUNS_DIR` when changing models or task selection.

## Execution boundary

The upstream benchmark executor has unrestricted network access and the Codex substrate bypasses its own approval, sandbox and hook-trust checks. Execute model-backed experiments only inside an independently isolated benchmark environment with the intended network restrictions and no unrelated credentials. Do not disable Xwav's guardrails or copy optimized guardrails, scripts, plugins or global instructions into a user's active agent automatically. Inspect proposed harness changes and evidence before applying them within the user's authorized scope.

If the runtime, credentials or benchmark dependencies are missing, report that limitation and the relevant setup step. Do not claim that a packaged skill or a passing local demo proves model-backed benchmark performance, interactive chat integration or production readiness.

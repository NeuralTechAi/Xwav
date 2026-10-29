---
name: penetration-testing-with-strix
description: Run explicitly authorized security assessments with the optional Strix CLI, inspect vulnerability reports, and help fix verified findings. Requires a scoped target, budget and configured runtime.
license: Apache-2.0
---

# Strix in Xwav

Adapted from usestrix/strix at the revision in `integrations.json`. The reviewed
CLI is `strix-agent==1.7.0`. Xwav supplies this one canonical skill for the Strix
workflow. Skill discovery never starts scans or installs software. The dashboard
automatically scans the current project on opening, installs the isolated CLI
on demand and reuses Xwav’s free model gateway. Docker must already be available. Do not install another Strix
skill collection or change other agents' global configuration.

## Scope and prerequisites

Strix actively tests targets and can validate exploits. Before execution, obtain
an explicitly authorized target and scope, permitted actions, a budget and the
chosen local or managed execution mode. A local target is mounted writable;
use a clean disposable checkout if modifications would otherwise risk work.
Do not expand the target or start scheduled scans automatically.

For local execution:

1. Check an existing `strix --version` and `docker info`.
2. The reviewed version needs Python >=3.12 and a running Docker daemon.
   If installation is needed, explain these requirements and use an isolated
   environment with `strix-agent==1.7.0`; do not run a curl installer or install
   system dependencies automatically.
3. Configure a supported model via STRIX_LLM and credentials via LLM_API_KEY,
   or an existing supported sign-in. Keep secrets outside chat and source files.
   The first scan may download the sandbox Docker image and consumes provider
   tokens; installation of this skill does not authorize that download or spend.
4. If prerequisites or authorization are missing, state the blocker and continue
   useful static code review without claiming a dynamic assessment occurred.

## Run and inspect

Use the CLI in non-interactive mode, set the user's budget explicitly and quote
the authorized target. For example, after the user authorized that path and a
$5 limit:

```bash
strix -n --target /absolute/path/to/disposable-checkout --scan-mode quick --max-budget 5
```

Use `strix --help` to confirm the installed release's options before invocation.
Use `--instruction-file` for detailed scope instructions instead of embedding
credentials in command arguments. Results are stored under `strix_runs/`.
Run from the current Xwav job workspace so its Penetration Test dashboard can
read `strix_runs/<run-name>/run.json` and `vulnerabilities.json` (or the legacy
`scan_data.json`). Preserve Strix's real scan state and evidence; never invent
findings or a completed result. Opening the dashboard starts a managed full-project
scan on a disposable snapshot; Run again creates a fresh scan. Historical run
links remain read-only. Scans are bounded to 20 turns and 30 minutes, with only
zero-cost models eligible. Do not expand this project-local authorization to
remote targets.
The local dashboard can be opened with `strix view`; its tokened URL grants
access to results and should be treated as private.

Read the actual findings and supporting evidence. Distinguish verified issues
from guesses, explain reproduction conditions, and implement fixes using the
project's normal tests. Rescan only the already authorized scope and remaining
budget. Do not turn an inconclusive result into a claim of security.

## Optional managed cloud and CI

Managed mode uses `strix cloud` and a separately configured app.strix.ai account.
It can send target content to remote infrastructure. Choose this mode only when
the user authorizes it; missing Docker is not consent to upload source or use a
paid service. Never purchase credits, top up, subscribe, or change billing
without the user's separate explicit approval. Read `strix cloud --help` and the
[official cloud documentation](https://docs.app.strix.ai) for current account and
scan commands. Local and cloud mode have different prerequisites; report which
one actually ran.

For CI, consult the [official Strix documentation](https://docs.strix.ai), keep
credentials in the CI secret store, and add an explicitly requested scoped job.
Do not create recurring jobs or enable automatic PR scans merely because this
skill is available. No separate managed, CI, or vulnerability-fixing skill needs
to be installed; this adapter covers those entry points.

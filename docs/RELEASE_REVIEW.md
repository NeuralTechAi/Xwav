# Build, deployment and download review — 25 October 2026

The review covers Release Studio's deployment and package pages, transported job
workers, automatic tool setup, package verification, and job/project source ZIPs.

## Fixed findings

| Finding | Result |
| --- | --- |
| Deployment destination field updated the wrong state and could permanently disable Build | Stable input, debounced readiness, provider changes clear the previous destination |
| No web package option in Downloads | Web builds and authenticated ZIP downloads alongside native packages |
| Long commands showed no output until they exited | Bounded live log tails, with environment-secret redaction |
| Invalid release settings prevented cancellation | Status and cancellation remain available; invalid settings block starting a new build |
| Mobile/desktop conversion missed build:web and prebuilt exports | Shared web build detection and prebuilt dist/build/out/www support |
| Missing pnpm/yarn/bun CLIs despite declared project requirements | Versioned, private, lazy package-manager installation and caches |
| Remote provider builds redundantly installed local project dependencies | Remote Vercel/Railway builds delegate those steps to the provider |
| Old native packages could be reported as new after a no-op build | Unchanged packages require previous successful provenance for the same source/target |
| Downloads trusted only the report entry | Actual job file size/SHA-256 verified before streaming; stale, missing, changed and symlink packages rejected |
| Browser could save incomplete package bytes | Received byte count checked before saving |
| Generated applications always used initial version metadata | Configured/package version, Android versionCode/versionName, iOS marketing/build versions, explicit build number for automatic store submission |
| Cached mobile wrappers retained an obsolete application identity | Identity changes regenerate the framework-owned native wrapper |
| Worker code approached shell argument limits | Transport bootstraps a single compressed worker source |
| Workspace-relative executable commands failed readiness | Executables resolve relative to the selected project workspace |
| Damaged old reports or interrupted cached tools could block future builds | Invalid historical reports are ignored; missing cached executables are downloaded again |
| Source ZIPs could include large generated release folders | Generated .xwav/releases omitted; release settings retained |

## Validation

- Broad backend regression run: **495 passed** across session resources,
  releases, tool setup, source archives, pre-production tests and load testing.
- Final targeted run: **71 passed**, including two additional regression cases
  added after the broad run started (relative executable and generated-cache
  export exclusion). This brings distinct backend coverage to **497** cases.
- Frontend: **20 passed** across Release Studio and both composer entry points.
- Browser: **4 desktop/mobile journeys**, exercising real server/runner
  transport, provider text entry, local deployment workflows, Android fixture
  packages, web ZIPs, refusal of tampered packages, and job/project source ZIPs.
- Real disposable web project: pinned pnpm installation, real dependency
  installation, build:web execution and ZIP verification; a second build reused
  the tool/dependency cache. No cloud publishing was involved.
- TypeScript project compilation, production frontend build, Python lint,
  formatting and whitespace checks passed.

The broad suite produced three existing pytest-rerunfailures socket/thread
warnings; all product assertions passed. Browser screenshots and recordings,
command logs, and the disposable build report are retained under /tmp, outside
tracked product files.

## Boundaries

Provider command/configuration paths were tested locally; this review did not
publish to paid or production provider accounts. Android fixture packages verify
transport/format, not native compilation or device installation. No signed iOS
build or Google Play/App Store submission was performed. Those require the
user's SDK licence, Mac/cloud builder, accounts and signing configuration.

The previous on-demand provisioning validation produced an actual unsigned
Windows NSIS EXE; its evidence is recorded in RELEASE_STUDIO.md. This review
extends version/configuration tests and does not claim a new signed Windows
release or a device installation test.

Compatible browser frontends can be packaged. Backend services still require
hosting; unsupported native frameworks use a project-defined/cloud workflow.
Store submission success is distinct from store approval.

## Human verification

1. Refresh Xwav and open Deployments from a saved job. Select Cloudflare Pages,
   type a project name, and confirm readiness becomes actionable without losing
   the text. Choose the actual configured destination before publishing.
2. Open Installable downloads, choose Web, build and download the ZIP. Check its
   index.html and assets. Native platforms use the same progress/download flow;
   Android's first automatic setup requires SDK licence acceptance.
3. Start a configured longer build, observe its live log and use Stop. A failed
   or cancelled run must not offer an executable package.
4. Download the job/project source ZIP after building. It should contain source
   edits and .xwav/release.json, with no generated .xwav/releases tree.

See [Release Studio](RELEASE_STUDIO.md) for app identity, version/build settings,
provider setup and custom native/cloud workflows.

## Cloud build and publishing implementation — 25 October 2026

Added GitHub Actions as a build-computer option in both Release Studio pages.
Preparation writes reviewable workflow/worker files into the selected project's
Git root. Connection checks use the job's GitHub login and inspect repository,
workflow, selected environment, required secret names and production reviewers.
No signing key or provider token is saved in project source or browser storage.

The generated workflow selects Linux, macOS or Windows workers on demand,
checks out an explicit source SHA, prepares temporary mobile signing material,
runs the existing build engine, and uploads verified packages. Store adapters
select Play internal / TestFlight for testing. Production selects Play
production or App Store Connect binary upload; Apple review/release stays in
App Store Connect. Web testing uses previews, with explicit isolated staging
configuration required for Railway/custom scripts. Existing custom commands are
preserved. Cancellation requests stop the remote workflow when its run appears.

Cloud dispatch uses the repository's default branch to load the workflow, and
passes the immutable project commit separately to checkout. The worker verifies
its checkout against that input and returns the source commit in the artifact
manifest. This follows the GitHub workflow-dispatch branch/tag contract rather
than assuming an arbitrary SHA is a valid dispatch reference.

Validation evidence (local files under /tmp, no production release):

- `/tmp/xwav-cloud-final-backend.log`: 140 backend regression checks passed,
  covering releases, tool setup, quality checks and owner-only release APIs.
- `/tmp/xwav-cloud-last-targeted.log`: 67 cloud/local build checks passed after
  adding cloud setup files to artifact provenance tracking.
- `/tmp/xwav-cloud-last-cloud.log`: final 27 cloud checks passed, including
  generated-worker web compilation/ZIP creation, rejection of a mismatched
  checkout, dispatch correlation after branch movement, store channel command
  selection, temporary credential cleanup and corrupt archive/package refusal.
- `/tmp/xwav-cloud-final-ui.log`: 23 frontend checks passed across the dashboard
  and composer navigation. TypeScript project checks passed.
- `/tmp/xwav-cloud-browser-final.log`: desktop and phone journeys cover workflow
  preparation and production controls on Deployments, connection controls on
  Installable downloads, real local fixture builds/downloads and tampered
  download refusal. Recordings are in `/tmp/xwav-cloud-browser-final/`.
- Production web build, Ruff, Prettier and Git whitespace checks passed. The
  existing large-bundle advisory remains. Pytest reported its known socket
  cleanup warnings; product assertions passed.

A real generated cloud worker built a static web package locally without an
installed Xwav package. GitHub HTTP/store calls in contract tests use doubles.
No paid hosted runner, Android SDK compilation, signed iOS archive, developer
account or live store upload was exercised. Credential presence checks do not
prove that credentials are valid. The next account-backed acceptance checks are
an Android install plus Play internal upload, a signed iOS build plus TestFlight
installation, and a web preview deployment. See RELEASE_STUDIO.md for exact setup.

## Android/iOS release actions — 25 October 2026

The previous dashboard disabled mobile actions for missing SDK consent, signing,
Mac/cloud setup or other readiness checks. This left users without a clickable
next step. Reproduced in the prior built UI: the Android deployment action
remained disabled in the real server/runner desktop journey.

Android/iOS primary actions now start ready jobs directly, or open guided setup
when requirements are missing, pending or temporarily unavailable. Setup shows
the blocker, accepts SDK consent and production confirmation when needed,
provides a retry, and opens the relevant cloud panel. Backend prerequisites are
preserved. Busy/running jobs still prevent duplicate starts.

The extended browser journey also exposed a previous-package race: an old IPA
could remain clickable while a new build request was pending. Previous packages
are now hidden immediately during submission, completed state follows the
selected platform, and downloads are guarded against busy/running/stale state.

Validation:

- 34 frontend checks passed: both platforms in deployment/download modes,
  missing prerequisites, direct ready starts, SDK/production consent, pending
  readiness, retry after a connection failure, stale-package submission state,
  and existing composer/download behaviors.
  Log: `/tmp/xwav-mobile-buttons-regression-ui.log`.
- 84 build runtime, cloud and toolchain checks passed.
  Log: `/tmp/xwav-mobile-buttons-backend.log`.
- Desktop and 390px phone browser journeys passed through the actual isolated
  server/runner. Both platforms opened setup for gaps, then ran local fixture
  deployment commands and produced/downloaded APK/IPA fixtures. Existing web
  package and tampered-download checks also passed.
  Log: `/tmp/xwav-mobile-buttons-verified.log`; videos/screenshots:
  `/tmp/xwav-mobile-buttons-verified/`.
- TypeScript, production build, Prettier, Ruff and whitespace checks passed.
  The existing large JavaScript chunk advisory remains.

These native package fixtures verify controls, transport and download handling;
they do not exercise Android/iOS SDK compilation, real signing or store upload.
Refresh Xwav, select Android/iOS on either release page, and click the primary
action: it should start a ready project or show actionable setup requirements.

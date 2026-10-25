# Xwav Release Studio

After the chat's Load Testing icon, **Deployments** and **Installable downloads**
open separate pages pinned to the job (or the latest saved job in a project).
Hover each icon for its description. Opening a page only checks readiness; it
never starts a build or publishes an app. Choose a platform and destination,
then start the action. Builds continue when the tab closes and can be cancelled.

## Web destinations

Users explicitly choose Vercel, Netlify, Cloudflare Pages, Railway or the project's
own deployment workflow. Authentication lives on the job's computer/container:
configure it there, including in each new isolated sandbox. Xwav never copies
host credentials into jobs for deployment.

| Destination | Connection / destination | Build behavior |
| --- | --- | --- |
| Vercel | Vercel CLI login or `VERCEL_TOKEN`; existing `.vercel/project.json` links are honored | Source is built by Vercel; job-specific links are cached for redeployment. New unlinked jobs get distinct project defaults. |
| Netlify | CLI login or `NETLIFY_AUTH_TOKEN`, plus linked site or selected site ID | Build static frontend, then deploy its staged output to production |
| Cloudflare Pages | Wrangler login or `CLOUDFLARE_API_TOKEN` / account setup; existing Pages project name | Build static frontend, then deploy its staged output |
| Railway | CLI login or `RAILWAY_TOKEN`, with linked project/service; optional service choice | Upload staged source and wait for provider build/deployment; public domain must be configured in Railway |
| Project workflow | `deploy:web` / `deploy` package script, or configured argument array | Use the project's connected deployment system |

First-party source uploads omit local environment files, signing keys, job state,
Git metadata and dependency/build caches. Existing Vercel project-link metadata
is preserved separately. Static packaging omits environment files and symlinks;
configure a dedicated output directory for production assets. Remote runtime
secrets/private package registry access must be configured at the destination.
Project-defined commands are trusted project code and control their own uploads.

Provider references: [Vercel deploy](https://vercel.com/docs/cli/deploy),
[Netlify CLI](https://docs.netlify.com/api-and-cli-guides/cli-guides/get-started-with-cli/),
[Cloudflare Pages](https://developers.cloudflare.com/workers/wrangler/commands/pages/),
[Railway up](https://docs.railway.com/cli/up).

## Native conversion and installable packages

Compatible browser frontends can be packaged with Capacitor (Android/iOS) or
Electron Builder (Windows NSIS). This wraps the frontend; server processes do not
become mobile binaries, and backend APIs must remain reachable. Static output
must include `index.html`; SSR-only applications need a static export or their
own native build workflow. Android projects with a Gradle wrapper use their
existing native project; Capacitor projects rebuild/sync their assets and plugins.
Known Capacitor dependencies are carried into generated mobile wrappers.
Missing supported toolchains now initialize automatically when building; see
Automatic toolchain setup below.

- **Android download:** Gradle `assembleDebug` produces an installable development
  APK. Google Play publishing uses release signing and the project's configured
  publishing workflow (`bundleRelease` for the automatic Gradle path).
- **iOS:** a local build requires macOS/Xcode and `.xwav/ExportOptions.plist` with
  the user's provisioning/export settings. `teamID`, when present, is passed to
  archive signing. Signed IPA distribution depends on its provisioning profile.
  A configured cloud build can supply the IPA on another job platform.
- **Windows:** Windows or Wine and Node.js are needed for automatic NSIS builds;
  a custom/cloud build can also produce the EXE. Native build tooling is cached
  per job and platform. First-time downloads/builds can take several minutes.

[Capacitor prerequisites](https://capacitorjs.com/docs/getting-started/environment-setup),
[Capacitor workflow](https://capacitorjs.com/docs/getting-started),
[Windows packaging](https://www.electron.build/docs/win/).

The current transported worker runs in POSIX Python job environments, including
Linux containers and macOS. Windows installers can be produced by Wine or a
configured cloud build. It provisions missing build tools in a private cache without a system-wide SDK
installation. It does not provision Apple signing identities, create store
accounts, or bypass store review. Store workflow success
means submission completed; approval and availability remain with the store.

## Project configuration

Existing `build:web`, `build:android`, `build:ios`, `build:windows` and matching
`deploy:<platform>` package scripts are discovered automatically. For other
build systems or cloud services, save `.xwav/release.json` in the workspace:

```json
{
  "app_name": "My App",
  "app_id": "com.example.myapp",
  "web_output": "dist",
  "targets": {
    "android": {
      "build": ["bash", "scripts/build-android.sh"],
      "deploy": ["bash", "scripts/publish-google-play.sh"],
      "artifacts": ["build/**/*.apk", "build/**/*.aab"]
    },
    "ios": {
      "build": ["bash", "scripts/build-signed-ios.sh"],
      "deploy": ["bash", "scripts/publish-app-store.sh"],
      "artifacts": ["build/**/*.ipa"]
    },
    "windows": {
      "build": ["bash", "scripts/build-windows.sh"],
      "artifacts": ["build/*.exe"]
    }
  }
}
```

Scripts must exist and use the job's configured account credentials. Commands
are argument arrays, not HTTP-supplied shell strings. Only owners may inspect,
start, cancel or download release artifacts. Each job runs one release at a time;
different jobs can build concurrently. A source change during building blocks
publishing; source/config changes also mark a completed report stale.

Downloads expose only listed packages from the latest completed successful run,
with size and SHA-256. Format checks identify ZIP/APK/AAB/IPA containers and EXE
headers; they are not device installation tests or cryptographic signing
certification. AABs are store bundles and are not offered as direct installers.
Limits: 10,000 source files / 256 MiB tracked by content, a 30-minute worker
budget, bounded 2 MB command logs (16 KB report tail),
20,000 staged files / 256 MiB assets or upload source, 20 packages / 512 MiB total.
Build work directories are removed after completion; packaging tool caches remain.
JSON reports retain build status and bounded logs.

## Validation evidence

Runtime tests execute real local subprocesses and a static ZIP build; native
adapter/tool invocations and provider commands are tested with doubles. Browser
journeys on desktop/mobile exercise real job transport, local build/deploy fixture
scripts, separate tabs, provider selection and package downloads. Fixture APKs
validate the download pipeline, not actual device installation. No production
provider account, Google Play upload, Apple upload or signed native device install
was performed by these tests.

## Automatic toolchain setup

Build and Deploy now provision missing tools in the detached job worker. Opening
Release Studio or checking readiness never downloads software. Setup phases and
failures appear in the existing dashboard; cancellation and the 30-minute worker
budget also cover setup. Failed setup produces no downloadable installer.

- **Node.js:** the current official Node 22 distribution and SHA-256 manifest,
  selected for Linux/macOS x64 or ARM64, are used when Node/npm are missing or Node is older than 22.
- **Android:** managed Temurin JDK 21 (unless JAVA_HOME is supplied) and versioned
  Google command-line tools are downloaded with SHA-256 verification. The owner
  must accept the linked Android SDK licence in Release Studio before the first
  automatic setup. SDK licence acceptance is retained in that job's SDK cache.
  Gradle downloads the SDK packages required by the project's configuration.
  Automatic SDK provisioning supports Linux x64 and macOS Intel/Apple Silicon.
- **Windows on Debian/Ubuntu x64:** Wine and its missing dependencies are fetched
  using signed APT repositories, then extracted into the private tool cache.
  The 32-bit Windows DLLs needed by NSIS are provisioned alongside the 64-bit
  runtime; setup checks a Windows command before packaging starts.
  Xwav does not run sudo, install OS packages, or mount a Docker socket. Existing
  Wine can be reused. Other platforms need a suitable computer or custom cloud
  build workflow. Generated installers are unsigned unless signing is configured.
- **iOS:** use a Mac with Xcode/signing or the existing custom cloud build command.
  Xwav does not download Xcode or create a cloud account automatically.

The default cache is `~/.cache/xwav/build-tools/v1`, outside project source and
release uploads. Repeated builds reuse completed tools and packaging libraries.
Interrupted downloads are discarded; cache locks prevent overlapping setup.
Each Docker job has its own cache and credentials. Administrators may set
`XWAV_BUILD_CACHE` to a persistent location scoped to one trusted user; no writable
cache is shared across unrelated users. Removing a job container removes its
unmounted cache. First builds can download hundreds of MB and take minutes.
Temporary unpack directories are removed on completion/error, and Wine package
archives are removed after extraction. Failed run outputs and successful run
intermediates (such as unpacked Electron applications) are removed; only listed
packages are retained. npm, Electron and Gradle downloads also use the build cache. Existing job sandboxes keep running for
chat; the detached build worker exits when the build finishes.

Provider and store account connections remain a one-time prerequisite. Custom
build/deploy commands retain control over their cloud service setup. No build is
published merely by visiting the page or selecting a target.

### On-demand provisioning smoke evidence (24 October 2026)

A disposable, non-root `xwav-host:local` container downloaded and verified the
actual official Node 22 and Temurin JDK 21 archives, executed both runtimes and
reused their completed caches. Rootless Wine provisioning was verified with an
actual Windows command, including Debian launcher/data relocation, native zlib
DLLs and 32-bit Windows installer compatibility files. The normal transported
release worker then built a real unsigned NSIS EXE from a static frontend:
112,981,840 bytes, SHA-256
`b5295f75427344dd8c29e371893b4aced5093d2f0caa08b113246fb1e3076b0c`.
The package hash was independently checked before cleaning the disposable cache.
This verifies packaging, not installation or execution on a Windows device.

Desktop and actual phone-width browser journeys cover Android SDK consent,
readiness, explicit build/deploy actions, logs and download transport. Android SDK
compilation was not run without the user's SDK licence acceptance. No signed iOS
build, production deployment or store submission was performed. These continue
to require the user's platform environment and account/signing connections.

## Release review improvements (25 October 2026)

The downloads page now includes **Web** for a built static ZIP, alongside native
packages. Deployment destination text stays editable while readiness checks are
debounced; changing providers clears the previous destination. Active build logs
are streamed as bounded, redacted tails instead of waiting for a command to exit.
Cancellation remains available when project release settings become invalid.

Build detection supports prebuilt `dist`, `build`, `out` and `www` exports and
uses a configured web build, `build:web`, then `build` when preparing mobile or
desktop wrappers. Declared package-manager versions are used, with private lazy
installation for pnpm/yarn/bun. Standard locked installs remain frozen. First
pnpm builds without a lockfile avoid generating a source change. Vercel/Railway
remote builds skip redundant local dependency installation.

Generated app metadata can be configured in `.xwav/release.json`:

```json
{
  "app_name": "Example App",
  "app_id": "com.example.myapp",
  "app_version": "2.3.4",
  "build_number": 42,
  "web_output": "dist"
}
```

Windows uses the configured version (or package.json version). Generated Android
wrappers set versionName and versionCode. Generated iOS archives pass marketing
and build versions to Xcode. Automatic store submissions require an explicit
positive build_number; increment it for each submission. Existing native projects
and custom/cloud workflows own their own native version/signing settings.
Changing generated mobile app identity recreates that generated native wrapper.

An old package is accepted as a cached build only when its content matches a
previous successful run for the same source and target. A no-op build after a
source change cannot silently publish an older package. Downloads reject stale
source reports, missing files, symlinks, size/checksum mismatches, or incomplete
runs. The job hashes the actual file immediately before streaming; responses
include X-Artifact-SHA256 and ETag, and the browser checks the received byte count.
JSON reports include bounded logs and remain downloadable separately from executable packages.

Review validation includes a real pinned pnpm install, dependency installation,
`build:web` execution and ZIP verification in a disposable project. Browser tests
exercise desktop/phone layouts, provider inputs, local deployment fixtures,
Android fixture downloads, web ZIPs, rejection of modified packages, and project
source ZIPs. Provider credentials, paid production deployments, native mobile
compilation/signing and store review remain separate prerequisites; local fixtures
and format checks do not establish those external outcomes.

Project source ZIP exports preserve `.xwav/release.json` while excluding the
generated `.xwav/releases` trees, so native build caches and large installers do
not inflate or prevent source downloads. Download finished packages separately
from Release Studio.

## Managed cloud builds and store connections

Release Studio now offers **Build computer → GitHub Actions** on both the
Deployments and Installable downloads pages. Local jobs remain available. The
cloud option runs Linux Android/web builds, macOS iOS builds and Windows desktop
builds without putting those SDKs into the Xwav server. GitHub may bill runner
minutes. Only explicit start actions dispatch a workflow.

1. Authenticate GitHub **inside the owning job**, using `gh auth login` or a
   job-scoped `GH_TOKEN`. No host account is copied automatically. Restrict a
   fine-grained token to this repository: Contents read, Actions read/write,
   Environments read and environment Secrets read for readiness checks.
2. Enter `owner/repository` and click **Prepare cloud workflow**. This creates
   `.github/workflows/xwav-release.yml`, `.xwav/cloud.json`, bundled worker
   modules under `.xwav/cloud/`, and generated-output exclusions in `.gitignore`.
   It never commits, pushes or overwrites a different existing workflow. Review,
   commit and push these files to the repository's **default branch** so GitHub
   enables manual dispatch. Only repository-root projects are currently supported.
3. Open the provided GitHub environments link. Create `xwav-build`,
   `xwav-testing`, and `xwav-production`. Put each environment's credentials in
   **environment secrets**, not files, repository source or Xwav browser storage.
   Production must have required reviewers; if your GitHub plan does not support
   this protection, Xwav blocks production cloud publishing.
4. Configure the selected platform below; select **Check connection & signing
   setup**. This verifies repository access, the workflow, the selected
   environment/protection and required secret *names*. It cannot validate key
   contents or guarantee a store accepts a package; those checks happen in the
   actual build/upload.
5. Select platform and destination, accept Android SDK licences when applicable,
   and start. Source must be committed and available in the selected GitHub
   repository. The workflow checks out the exact local HEAD commit, not a moving
   branch or unsaved changes. Its default channel is **Testing**. Production
   requires an explicit checkbox plus the GitHub environment's approval.
6. Follow the linked worker logs/approval. Xwav polls in the background and
   retrieves the run's artifacts on success. It checks commit, platform, action,
   channel, package structure, size and SHA-256 before offering downloads.
   Modified local source invalidates download readiness. Stop requests remote
   cancellation; uploads already accepted by a provider cannot be undone.

### Environment secrets

Android development APK downloads need SDK licence consent but no Play account.
Android store builds need `app_id`, `app_version` and a unique positive
`build_number` in `.xwav/release.json`. Configure:

- `XWAV_ANDROID_KEYSTORE_B64`: base64 upload keystore.
- `XWAV_ANDROID_KEYSTORE_PASSWORD`, `XWAV_ANDROID_KEY_ALIAS`,
  `XWAV_ANDROID_KEY_PASSWORD`: its signing settings.
- `XWAV_GOOGLE_PLAY_JSON`: service account JSON authorized for this app in Play
  Console. Create the app and complete its initial console setup first.

The cloud worker injects the upload signing configuration into Gradle and
verifies that the AAB has a JAR signature before uploading. Testing goes to
Google Play's **internal** track; production goes to its **production** track.
Play review/policy restrictions still apply. Keep and back up the upload key;
use Play App Signing for store distribution.

iOS build and upload environments need:

- `XWAV_IOS_CERTIFICATE_B64`: base64 signing certificate plus private key (P12).
- `XWAV_IOS_CERTIFICATE_PASSWORD`: P12 password.
- `XWAV_IOS_PROFILE_B64`: base64 provisioning profile for the app ID.
- `XWAV_IOS_EXPORT_OPTIONS_B64`: base64 ExportOptions.plist, including your team
  and profile mapping/distribution method. For the default generated app the
  target/bundle is configured from `app_id`; native projects may supply a custom
  build command in release.json.
- For uploads, `XWAV_APPLE_API_JSON`: fastlane API key JSON with `key_id`,
  `issuer_id` and `key` (the private P8 text). Use an appropriate App Store Connect
  role. The app must already exist in App Store Connect.

The worker imports the certificate into a temporary keychain and installs the
profile, then removes them during cleanup. Testing uploads to **TestFlight**;
production uploads the binary to **App Store Connect**, without automatically
submitting review or releasing it. Complete metadata, review and release there.
An IPA's installability depends on its distribution profile. App Store IPAs are
not unrestricted downloads installable on arbitrary iPhones.

Web environments use `VERCEL_TOKEN`, `NETLIFY_AUTH_TOKEN`,
`CLOUDFLARE_API_TOKEN`, or `RAILWAY_TOKEN`. Set environment variables
`VERCEL_ORG_ID` / `VERCEL_PROJECT_ID`, `NETLIFY_SITE_ID` and
`CLOUDFLARE_ACCOUNT_ID` as appropriate. Testing uses Vercel/Netlify preview
uploads and the `xwav-preview` branch for Cloudflare Pages. Railway and custom
project scripts must have a separate staging destination; explicitly set
`XWAV_STAGING_CONFIRMED=true` in that environment after configuring it. These
providers cannot infer a safe staging destination from an arbitrary live setup.

Custom target build/deploy commands are preserved. Such commands own their own
signing/versioning/staging behavior; the standard cloud credential checks still
apply. Framework-owned cloud files are copied at preparation time: updating
Xwav does not silently change a reviewed project workflow. To upgrade one,
review the changed generated files and replace them deliberately.

### Verification boundaries

`tests/server/test_release_cloud.py` exercises generated workflow preparation,
source/auth/protection checks, dispatch/poll/cancel/artifact contracts, rejected
archives/checksums, credential cleanup and a **real standalone generated-worker
web build**. Provider/store operations use doubles; no live cloud run, native
compilation or store account is claimed by those tests. The desktop and phone
release browser journey prepares the actual workflow through the server/runner,
checks production gating, then exercises existing local builds and downloads.
SDK licence acceptance, developer enrollment, actual signing and store review
remain account-owner setup and must be validated with a first real signed build.

## Mobile action buttons and guided setup

Selecting Android or iOS keeps **Build & deploy** / **Build installer** actionable
on both Release Studio pages. If the selected job is ready, the button starts
immediately. If requirements are missing or readiness is still being checked,
the button opens a setup dialog instead of remaining disabled.

The dialog shows the current blocker and provides Android SDK licence consent,
production confirmation when needed, a readiness retry, and a direct path to
GitHub Actions setup. Choosing a cloud worker does not dispatch a build; the
repository/workflow and signing credentials still need configuration. The
Continue button only starts after readiness and the required consent checks
pass. Server-side prerequisite validation remains in force.

Verify this with a new job: choose Android or iOS on Deployments or Installable
downloads, then click the main action. Missing tools/signing should open setup;
ready configured projects should build directly. Android consent can be given
in the dialog before continuing. Stop remains available during running jobs.

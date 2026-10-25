# Deployments and installable downloads

Open the icons after Load Testing in either chat composer. Deployment and
installable pages open in separate tabs and preserve the job/project context.
No job: explain how to start one. Opening a page never publishes or builds.

Choose Web/Android/iOS for deployment. Web requires an explicit choice of Vercel,
Netlify, Cloudflare Pages, Railway or project workflow. Choose Windows/Android/iOS
for an installer or Web for a built ZIP. Check prerequisites and connection hints, start, observe logs,
cancel, or download completed packages and JSON reports. Missing supported tools are installed on the first explicit build. Android
requires SDK licence acceptance before starting automatic setup. Recheck
readiness after configuring signing or a cloud workflow. Unsupported targets and missing signing are gaps,
never successful app builds. Different jobs retain separate reports and caches.

See [Release Studio](../docs/RELEASE_STUDIO.md) for configuration, exact platform
support, prerequisites, limits and verification boundaries.

Verification:

- `tests/server/test_release_runtime.py`: real static build/worker transport,
  configuration and path validation, failure gates, source provenance, provider
  commands, native adapter generation and per-job cache reuse with doubles.
- `tests/server/routes/test_session_resources.py`: owner-only actions, valid
  provider options, read-only status, malformed results and completed artifact
  download permission gates.
- `web/src/components/composer/ComposerPreviewLink.test.tsx`: icon order,
  tooltips, separate tabs, session and project context.
- `web/src/pages/ReleasePage.test.tsx`: explicit provider choice, platform
  selection, no automatic publishing, gaps, cancellation and authenticated downloads.
- `tests/e2e_ui/sessions/test_xwav_workbench.py::test_release_pages_build_and_download_in_job_runtime`:
  desktop/mobile real runner transport using local build/publish fixture scripts;
  no production deployment, signed native compilation or store accounts involved.

- `tests/server/test_release_tools.py`: rootless setup, safe extraction,
  checksums, cancellation, cached reuse and Android licence gating.

Review journeys also cover provider destination typing, live build logs, private
package-manager setup, generated native versions, unchanged-package provenance,
actual package checksum validation, and refusal of tampered/stale downloads.
The desktop/mobile release journey downloads a web ZIP and verifies that a
subsequently modified package returns an error rather than a new download.

Cloud build setup is available from **Build computer → GitHub Actions** on both
pages. Explicit preparation writes a reviewable workflow and worker modules;
users commit/push them, configure protected GitHub environments, and check the
selected platform's connection. Testing is the default publishing channel.
Production requires a checkbox and environment reviewers. Worker logs/approvals
open on GitHub; downloads use the same verified artifact endpoint as local
builds. No account credentials are written by the setup action.

- `tests/server/test_release_cloud.py`: cloud setup, exact commit selection,
  secret-name/protection checks, store command destinations, artifact integrity,
  cancellation, and a real generated-worker web build without an Xwav install.
- `test_release_pages_build_and_download_in_job_runtime` also prepares cloud
  files and checks production controls on desktop and phone, then returns to
  the local build/download journey. Live GitHub/store publication remains a
  separate credential-dependent validation.

Android/iOS action buttons open guided setup when prerequisites or consent are
missing, including while readiness is pending. The setup dialog displays the
blocker, can accept Android SDK licences, can confirm production publishing,
can retry readiness, and can open the cloud setup panel. Ready configurations
start directly. Running/busy jobs still prevent another start.

`ReleasePage.test.tsx` covers blocked and ready Android/iOS actions in both modes.
The real server/runner desktop/mobile release journey now exercises both native
fixture deployment commands and APK/IPA fixture downloads, as well as SDK and
Mac/signing gaps. These are UI/transport/package checks, not native SDK builds
or live store submissions.

# Xwav workbench redesign

The workbench uses a persistent desktop navigation rail, a task launch surface,
and an open three-column set of draft starters. Its green-gray light palette
and ink/mint dark palette share the existing theme provider, settings and saved
preferences. Other palettes remain selectable. Existing session, terminal,
file, PR, approval and harness routes remain the functional owners of their
workflows.

## Design and verification contract

The primary job is selecting a workspace/harness and preparing a task. The
first screen keeps the composer and its configuration visible. Draft starters
fill and focus that composer; they never submit a task. Git, harness settings,
search and appearance are reachable from the desktop rail. Phones keep the
existing sidebar drawer and stack task starters vertically.

Target viewports are 1440×1000 and 390×844, each in light and dark mode. Controls
must stay within the viewport; long draft text must remain editable. Navigation
has named controls and a current-page indicator. Keyboard focus is visible,
reduced-motion settings remove decorative transitions, and starter touch
areas are at least 44×44. The rail theme switch uses the same persistent
`web-theme` selection as Settings → Appearance and native chrome.

| State | Trigger and visible behavior | Next action |
| --- | --- | --- |
| Loading | Host/agent discovery is pending; existing loading controls remain | Wait for discovery or inspect the host |
| Empty | No projects/sessions; the task composer, starters and import action remain | Choose a starter or connect a host |
| Error | Launch or setup fails; the existing specific notice stays below the composer | Fix setup or retry without losing the draft |
| Partial | Host or harness is unavailable; the configured selection and warning remain visible | Select an available host/harness or set it up |
| Success | A draft starter fills and focuses the composer; navigation reaches the selected page | Edit the draft and explicitly start, or continue in settings |
| Permission | Existing permission picker and approval flows remain in their original components | Choose the intended permission mode and handle actual approvals |

## Git and GitHub capability audit

Local Git/worktrees and the GitHub connection, PR details, changed files,
patches, labels, reviewers and checks are already integrated. Git 2.43.0 and
GitHub CLI 2.87.3 were present; the existing account passed an authenticated
read of the Xwav repository. No remote write was used as a test.

The existing `git-workflow-and-versioning` skill remains the local Git guide.
The original `github-ops` native skill covers issues, PRs, reviews, CI
and Actions through the existing tools. It does not install a second server,
credential store or competing GitHub agent. Standard name/content suppression
lets project/user skills override this default.

## Verification entry points

- `web/src/shell/WorkbenchRail.test.tsx`: routes, active state, search and theme.
- `web/src/shell/WorkbenchStarters.test.tsx`: draft choices and busy-state blocking.
- Existing landing/AppShell suites: editable draft handoff, no implicit submit,
  project headers, host/worktree selection, attachments and configuration.
- Existing sidebar/theme suites: drawer, lists, session actions and appearance.
- `tests/e2e_ui/sessions/test_xwav_workbench.py`: built SPA at both target
  viewports/modes, draft editing, no session creation, geometry, touch targets,
  theme persistence, Git/harness routes, search and screenshots.
- Existing theme/settings browser journeys: appearance and return navigation.
- Existing native-skill and runner GitHub suites: filters/provenance, PR
  discovery, files, labels, review metadata, provider failures and observer.

For a manual check, open the local Xwav app, use a task starter, edit its draft,
and confirm a session starts only after pressing Start session. On desktop,
use the rail to open Git connections, harness settings and search, then switch
light/dark and reload. On a phone, open the sidebar for navigation and use
Settings → Appearance for the same theme preference.

The GitHub/provider batch also exercises durable file locking. On this machine,
individual filesystem flushes sometimes took about 0.7 seconds, causing
intermittent one-second busy-lock failures in the existing disk-based provider
tests. The isolated provider diagnostic passed all 28 tests; the broader batch
of 551 tests passed with a private RAM-backed temporary directory. Production
lock timeouts and durability guarantees were preserved.

## Recorded verification results

| Verification | Result |
| --- | --- |
| Core landing, AppShell, navigation and palette component batch | 885 passed; affected landing/setup tests subsequently passed 674 cases after final copy updates |
| Sidebar and shared theme regression batch | 452 passed; three stale legacy-color assertions were corrected and the full 42-test custom-theme file passed |
| Final caption/selection contrast and custom-theme checks | 79 passed |
| Native catalog, Git/GitHub override deduplication and real Pi resource discovery | 31 passed |
| GitHub, PR registry, provider and native skill batch | 551 passed using a private RAM-backed temporary directory |
| Provider diagnostic on the local filesystem | 28 passed; earlier disk-contention failures are described above |
| Built SPA responsive, theme, settings and delayed-create journeys | 20 passed on the combined run; one ambiguous home-link locator was corrected |
| Operator branding after the exact-link locator correction | All 7 passed, covering the corrected case and custom headings/logos/settings copy |
| Production SPA and Storybook builds | Passed |
| Required source pre-commit checks | Passed, including Python/TypeScript, lint, formatting and generated theme CSS |

Browser recordings and four responsive captures are retained outside the tracked
source tree. They use the actual built SPA and isolated test data; they do not
claim a live model-provider turn. Authenticated GitHub validation was read-only.

The complete pinned-renderer visual suite passed **215 cases** on its clean
comparison pass. **86 maintained baselines** changed intentionally. The landing
and chat screens were reviewed at full size; all changed images were also
reviewed in contact sheets. Baselines were regenerated in the exact image
pinned by the repository, rather than an unpinned local browser.

## Harness discovery and launch intentions

Settings → Harnesses now includes Google Harness² as a benchmark workflow. Its
status is read from the server's optional pinned runtime, independently of the
chat host. The launch harness picker links to that workflow rather than treating
Harness² as an interactive chat executor. The details page refreshes status and
copies explicit terminal commands; it does not start a sweep when opened.

On the landing composer, Add → Session → Goal saves an editable completion
condition alongside the draft. Plan toggles the selected harness's native plan
mode where available; otherwise it adds a planning request to the first task.
The portable request asks the agent to wait for approval before changing state;
it does not replace native permission enforcement. Both intentions survive
settings navigation and are transported with the first task.

Secondary text uses stronger default colors in both themes, verified at 7:1 or
better against canvas, cards and sidebar. Workbench captions are larger and
carry more weight. Custom palettes and saved font preferences stay supported.

To verify manually, reload Xwav, search for Google under Settings → Harnesses,
open Harness² and refresh its runtime status. On a new session, type a draft,
open Add → Goal, save a completion condition, then toggle Plan. Check that the
draft stays intact and the goal can be reopened, edited or removed. Compare
labels and help text in both appearance modes, including on a narrow viewport.

## Default chat harness

Settings → General → Sessions and Settings → Harnesses both expose the same
Default chat harness preference. It is saved in this browser and included in
settings export/import. Explicit session and project choices take precedence;
using another harness for one session does not replace the pinned default.
Choose Automatic to clear the pin and restore remembered-choice selection.
Harness² remains an independent benchmark workflow.

To verify, select Codex as the default, reload, and open a new session. Its picker
should start on Codex. Select a different harness for that session, then start a
fresh session: Codex should still be the default. Change the saved default to Pi
and verify the next new session starts on Pi, showing setup status if needed.
Existing chat sessions keep their harness.

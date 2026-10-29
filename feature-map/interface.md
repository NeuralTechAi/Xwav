# Interface typography and icon help

Xwav uses a self-hosted variable Inter face with a 15px desktop and 16px mobile
interface default. Saved font family and size preferences still apply. Code,
terminals and file diffs retain their monospace treatment. Font preferences
change typography rather than the root spacing grid. Dashboards use consistent
captions, readable logs, aligned counters and clear focus rings in both themes.

Hover an icon control to see a short action description. Keyboard focus shows
the same help; Escape dismisses it. Existing dedicated tooltips take precedence.
The fallback covers dynamically loaded pages and portalled controls with one
delegated listener, without injecting scripts into project preview frames.
Touch activation does not leave a focus tooltip behind. Decorative SVGs are not
actions and do not receive descriptions. Accessible names, native titles and
existing description associations are preserved when the tooltip closes.

Verification: `IconHelp.test.tsx` covers fallback lifecycle, keyboard focus,
disabled controls, dismissal, touch/pointer focus, existing tooltips and embed
scope. `uiFontPreferences.test.ts` and `SettingsPage.test.tsx` cover defaults,
overrides and reset. `test_ui_font_size_scales_and_persists` exercises a real
browser and the locally bundled face. Check the home/chat/settings, Preview,
Quality/Security/Performance Labs and Release Studio in light/dark themes and
narrow viewports for overflow and clear icon descriptions.

## Chat Git actions

Both user and assistant message toolbars place **Stage changes** and **Commit
changes** immediately after Revert and before Copy link. Hover/focus descriptions
explain each action. Stage reviews current project changes before `git add -A`;
Commit requires a message and commits only the reviewed staged index. Neither
operation pushes to GitHub. Ignore rules and unstaged edits are preserved.

The owner-only `/v1/sessions/{id}/git-actions` endpoint uses the existing runner
shell and session-family history lock. Jobs and child agents must be idle. A
changed index or HEAD requires a new commit review. Missing Git repositories,
identity, hook failures and runner errors appear in the dialog. New projects can explicitly initialize a local repository in the dialog; default
local exclusions cover dependency folders and .env files. Author identity and
credentials are not silently created. If Git has no author identity, the Commit
dialog collects a name and email for that commit without changing global config. The workspace must be the
repository root to avoid changing a parent project's staging area.

Validation: `GitMessageActions.test.tsx` and `ChatPage.userBubble.test.tsx` cover
placement, staged review, messages, cancellation, errors, live-state gating and
job switches. `test_workspace_git.py` uses temporary real repositories for first
commits, deletions/renames, ignored files, staged/unstaged versions, stale reviews,
command quoting and workspace scoping. Resource-route tests cover idle checks,
errors and ownership. To verify manually, open an idle Git-backed job, hover the
two icons, stage its intended changes, then enter a message and commit. Inspect
Git history; publish through the existing Git/GitHub workflow when ready.

Git review dialogs constrain height to the visible viewport and scroll long
content. Footer actions wrap within the panel; initialization and footer button
labels can wrap without clipping. Browser checks reproduced the former 307px
panel overflow and verified the fix at that width with default and enlarged
text, at 640×360 landscape, and at 320×568 mobile. All controls remained inside
the panel, with no horizontal overflow and the mobile footer reachable by scroll.

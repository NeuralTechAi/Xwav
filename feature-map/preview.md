# Live project app preview

The periscope icon sits above the left edge of the input box, in both the new-job
composer and an existing job/session composer. Hover explains its action. Opening
a separate browser tab leaves the main composer in place and carries the exact session id; a new-job composer in a project carries the
project name and selects that project's latest active job. It never chooses an
unrelated job. A project without a job shows a waiting state.

## Sub-features

- `automatic`: select the current job's HTML app without entering a URL.
- `devices`: Android and iOS above Web, with window controls and standby frames.
- `updates`: continue updating in a separate tab, including after its parent closes.
- `change-request`: select a visible region in any device and send a text request to the same job.
- `unavailable`: wait for a runnable app, published remote endpoint or dependencies.

## How to get to it (user POV)

- Click the periscope above the input on an existing project job.
- Click the same icon on a project's New Job composer to use its latest active job.
- Use the crosshair in any live panel, drag or click to highlight a region, then
  describe the requested change below that panel and choose Request change.
- A standalone New Job without a project shows standby screens until it has a job.

## Driving it with the repro environment

Preconditions: start the isolated environment from
[Verify Omnigent](skills/verify-omnigent/SKILL.md).

`tests/e2e_ui/sessions/test_xwav_workbench.py::test_preview_viewports_and_window_controls`
opens a job's composer icon and checks all device interactions, window controls,
layout and source updates in an independent tab. The standby entry point uses
`tests/e2e_ui/sessions/test_xwav_workbench.py::test_preview_standby_device_frames`.
Both run on desktop and mobile. Real runner discovery regressions are covered by
`tests/server/test_preview_runtime.py`, including misleading WebSocket listeners
and nested static exports without dev/start scripts.

## Gotchas

The independent tab connects automatically through the authenticated, owner-only
session runner shell API. There is no URL input. The runtime searches for web
listeners whose process working directories belong to this workspace. Otherwise
it starts the project's dev/start script using its lockfile's available package
manager, with Vite/Astro/Nuxt, Next and Expo web flags where appropriate. Static
`index.html` projects use a lightweight Python HTTP server. An
Electron app with a static renderer uses that HTML directly (including `src`,
`renderer`, `app` or `www` entry directories), rather than launching a desktop
window in a headless sandbox. A dedicated web `dev` script takes precedence.
Electron preload/IPC APIs still require a browser implementation in the project;
this preview does not emulate native desktop APIs.
Opening Preview reconnects a sleeping job runner through the same owner-authorized
recovery used by terminal creation, without sending a chat message.
A single runnable
app can live in a workspace subfolder. Static exports in `dist`, `build` or
`public` can run without a dev/start script and refresh when those files change.
Ambiguous multiple apps require a root `.xwav/preview.json` command. Discovery
accepts successful HTML pages only, excluding API/error responses and framework
control listeners such as Codex WebSocket servers. Dependencies must
already be available; preview does not install packages or invoke an LLM.

Hot-reload frameworks keep their own live update connection. Other app servers
and static HTML refresh automatically when a bounded source metadata scan detects
changes. Polling runs every three seconds while the preview is open, including when it
is unfocused. Focus and network reconnection also refresh status. Closing the
preview releases its polling subscription. The main tab can navigate away or
close without breaking the job connection. Browser/OS suspension can still
pause background execution until the tab resumes. Separate
workspace process records and locks avoid duplicate launches and cross-project
server selection. Minimize/maximize preserve each frame; close unloads it.

Android and iOS occupy the top row on wider screens, with the full-width web
preview below. Narrow screens stack Android, iOS, then web. The web frame has
a tab strip, address bar, reload/open controls and connection status footer;
history arrows and device system bars are decorative chrome. Reload affects
only the web frame.

The three frames load the actual app, not screenshots or generated mockups. Web
uses 1440×900; Android 412×915; iOS 393×852, with phone rotation. CSS-only Android and iPhone frames, status bars, camera
details and navigation bars surround the live viewport; standby screens retain
the device appearance before an app exists. No emulator is started. Android and iOS
are browser layouts using the current browser engine, not native APK/IPA or
Safari emulation. Native-only apps require native test runtimes.

Currently the automatic browser connection supports local workspaces and the
local Docker provider's host network. Remote hosts need published/tunneled ports;
that transport is not implemented here. The page reports that boundary rather
than connecting to an unrelated loopback server. Browser embedding restrictions
remain in force; the live app can also open in a full browser tab.

Unrecognized projects wait for the app to become runnable. A project may declare
`.xwav/preview.json` with a `command` argument array and `{port}` placeholders
for other development runtimes; it executes under the owner's existing job
permissions, with no shell interpolation.

Verification: `tests/server/test_preview_runtime.py` tests real automatic startup,
workspace isolation and file updates; server resource tests cover the existing
owner-shell boundary and invalid runtime results. Component tests cover automatic
session context and frame lifecycle. The workbench browser tests click the icon
above a real job's input, start a real static app, interact with each viewport,
and confirm that changing its source updates all three panels without URL entry
or a manual reload.

Region selection overlays the actual iframe, so cross-origin apps need no injected
script. Coordinates are translated from the displayed frame scale to CSS pixels
in its current viewport, including rotated phones. The request includes device,
viewport size, preview entry URL, selected bounds and user text. It is sent as a
normal user message to the exact connected job, under the existing permission
and checkpoint rules. This selects visible regions, not DOM nodes; no screenshot
is attached. Users should describe the intended element/change. Navigate or scroll
the app before selecting; embedding and native-runtime limits still apply.

Keyboard users can focus the crosshair, press Enter, then Enter on the selection
surface to select the center region, or Escape to cancel. Touch/pointer users
can draw any region. Closing the area keeps the text draft; minimizing preserves
it. Reloading, rotating or a source revision clears stale coordinates and keeps
the draft for reselection. Standby cannot be selected. Failed/denied sends keep
the draft and show an error; identical retries reuse their send identity. Sending
never claims an edit is complete; changes appear through the normal live preview.
The existing desktop/mobile viewport journey sends a selection from all three
frames and verifies each request and mock response in the real job chat.

Every preview request targets the shared app across Web, Android and iOS. The
selected device supplies visual context, not a device-only scope. Requests ask
the job to update shared components/styles/behavior, preserve responsive layouts,
and verify all three viewport sizes. All panels use the same app endpoint and
source revision, so completed source changes propagate across the live views.

Servers are probed for support of revision query parameters. Exact-path servers
that reject query strings load their plain entry URL and remount on revisions.
Servers supporting query strings carry a source-revision query parameter so rapid static edits bypass
second-resolution HTTP modification caches and refresh every device view.

Entering selection mode and focusing its editor preserve the page scroll position.
A stable scrollbar gutter and disabled scroll anchoring keep frame widths and
positions steady as selection controls appear. The live desktop/mobile journey
checks scroll position and frame geometry when each crosshair is activated.

Selection painting coalesces pointer moves into one animation-frame update,
without rerendering the app panels or measuring layout on every move. Bounds
are refreshed after scrolling/resizing and at release; pointer capture handles
frame-edge drags and ignores unrelated fingers. Clicks identify an exact point
instead of expanding to a large box. X/Y/Width/Height controls refine committed
regions in CSS pixels. Arrow keys move one pixel and Shift+arrows resize before
Enter confirms. Tests cover fractional scales, reverse/tiny drags, bounds,
cancellation, multiple pointers, scroll invalidation and frame coalescing; the
live desktop/mobile journey checks live highlight alignment to one display
pixel and sent coordinates to one CSS pixel on all three devices.

Automatic source refreshes hold the selected panel's iframe steady while a region
is being chosen, edited, or submitted. Other panels continue refreshing. Sending
successfully or clearing the region releases that panel and applies the newest
source revision. Late iframe load events cannot discard the editor, and source
polling cannot reset a pending send or its acknowledgement. Hot-reload frameworks
continue managing their own in-frame updates. The browser journey exercises source
changes during editing and a mock-driven agent file write after each device's
request, then verifies the resulting app in all three frames.
The main job chat stays open throughout: each request appears exactly once,
the working indicator and file-write activity stream in live, and completion
appears without navigating or refreshing the chat. A controlled model-response
gate keeps the in-progress state observable on desktop and touch layouts.

Runner-local file and shell tools resolve their workspace through the same
session resource registry as Preview. This preserves per-job workspace isolation
and the tool's own sandbox specification, rather than writing to a separate
fallback directory that the preview cannot see.

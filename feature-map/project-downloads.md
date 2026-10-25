# Project and job downloads

Every existing job's **Conversation actions → Download project (ZIP)** exports its
current saved workspace (including a selected workspace different from the runner's
launch directory), including uncommitted edits and untracked files. It is
available while the job is running or idle and does not commit or stop the job.
Chat history still has the separate Export action.

A project folder's kebab and context menu expose **Download latest job (ZIP)**.
This resolves the latest active job from the server independently of sidebar
pagination. Projects can have separate job sandboxes, so open a specific job to
download a different version. Empty projects explain that no active job exists.

Exports use the existing authorized filesystem API, including workspace sharing
rules. Symlinks, special files, Git internals and dependency/cache directories
are omitted. Source manifests and other project dotfiles remain included when
readable within the job's sandbox. Exports stop with an explicit error if a file
cannot be read, the workspace is unavailable, or the 512 MiB / 20,000-entry limit
is exceeded. A failed export never downloads JSON as a ZIP or a partial archive.
Server-side archive storage is temporary and streamed; no runner update is needed.

Verify desktop and mobile: create/edit saved files without committing, download
from the job menu and inspect the ZIP; download from the project menu too. Keep
chatting while downloading. Verify binary assets, nested folders, empty projects,
an unavailable runner, and a read-only collaborator with/without shared files.
Tests cover the shared menus, authenticated client, archive transport, limits,
invalid paths, pagination, errors and workspace permission boundary.

Automated entry points:

- `tests/e2e_ui/sessions/test_xwav_workbench.py::test_job_workspace_zip_download`:
  desktop/mobile job menu, project dropdown, desktop project context menu; checks
  the downloaded nested source and binary contents against the selected workspace.
- `tests/server/test_workspace_archive.py`: archive validation, pagination,
  selected workspace, omitted paths, read errors and export limits.
- `tests/server/routes/test_session_resources.py`: download transport and sharing.
- `web/src/lib/workspaceDownload.test.ts`,
  `web/src/shell/HeaderConversationMenu.test.tsx`, and
  `web/src/shell/Sidebar.projectContextMenu.test.tsx`: authenticated downloads,
  latest-job resolution, empty projects, error handling and shared menu actions.

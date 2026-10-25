# Project source folders

The Projects header **+** and **…** controls stay visible without hover, including
when the list is empty. Project folders also retain visible action menus, with
space reserved beside collapsed status badges.

**Projects → + → Create project** optionally selects a source computer and a
folder through the shared workspace browser. Browsing is provisional until
Confirm; Cancel preserves the name and previous folder. Changing computers
clears its old folder. The source can be changed or removed before creation.
No online computer: explain how to connect one and allow folder-free creation.

Creation saves the name, icon and folder defaults atomically via `POST /v1/projects`.
`config.host_id`, `config.workspace`, and explicit `config.source_folder: true`
make the selected connected computer and directory the new-job defaults. These
jobs edit that folder on that computer. Folder-free projects retain managed
sandbox isolation; an explicit managed-job choice never inherits a local path.
Existing project configurations without the source-folder flag keep their
previous execution behavior. Project settings can change the stored folder later.

Verification:

- `web/src/shell/NewProjectButton.test.tsx`: selection, removal, computer changes,
  cancellation, errors, no-host state, and atomic config persistence.
- `web/src/shell/NewChatDialog.projectPrefill.test.tsx`: source-folder defaults
  versus ordinary isolated projects, including the submitted create payload.
- `web/src/shell/Sidebar.test.tsx`: controls and collapsed status spacing.
- `tests/server/routes/test_session_create_project_consistency.py`: project
  defaults, access boundaries, folder-backed jobs and explicit managed overrides.
- `tests/e2e_ui/sessions/test_project_settings_dialog.py::test_create_project_with_source_folder`:
  desktop/mobile visibility at rest, real folder-browser controls, real project
  persistence and the new-job default. Its connected computer/filesystem is a
  browser contract double, so it does not claim a real host job execution.
- `tests/e2e_ui/sessions/test_project_rename_dialog_focus.py`: existing folder
  context/dropdown menu and project name focus behavior.

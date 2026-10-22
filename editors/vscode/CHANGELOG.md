# Changelog

All notable changes to the Xwav VS Code extension are documented here.

## [0.1.0]

Initial release — a minimal, iframe-only client for a locally running Xwav
server.

- Open a running local Xwav server in an editor-beside panel.
- **Xwav: Open** command, available from the editor-title bar and the
command palette, plus an activity-bar view with an "Open Xwav" button.
- Automatically discovers a local server via `~/.omnigent/local_server.pid`, or
point the extension at one with the `xwav.serverUrl` setting. Localhost
servers only in this build.


# Xwav Git and GitHub audit

The 2026-10-24 audit covers the existing GitHub connection flow, encrypted user
credentials and refresh, repository/branch access, GitHub resources, PR discovery
and diff reads. Tests use provider doubles or local repositories, not account
mutations. A separate real Git smoke exercise creates a temporary bare remote,
branches, commits, pushes, clones and pulls before deleting the temporary data.

The local host's `gh auth status`, GitHub account API and configured origin are
checked read-only. CLI authentication on a connected host is separate from a
GitHub App connection and from credentials inside an isolated Docker job.

The currently configured server has no GitHub App connection provider. Settings
→ Git now explicitly reports this state and offers the usual account controls
when the provider is configured. A missing optional status endpoint (404) means
“not configured”; authentication failures and server errors remain failures.

To enable browser account connection and per-user authentication for new managed
sandboxes, follow [GitHub App setup](GITHUB_APP_SETUP.md). This needs real GitHub
App credentials and repository installation access; an existing host CLI login
cannot substitute for that configuration. No host credentials are copied into
job sandboxes by this audit.

Validation: 224 Git/GitHub backend tests passed, plus six desktop/mobile browser
checks for connection controls, callback feedback, repository/branch selection,
and alternate entry points. Browser provider responses were mocked; host GitHub
account/origin read checks were live. The two inspected Docker jobs have no
GitHub CLI login, so their authenticated remote operations remain unverified.

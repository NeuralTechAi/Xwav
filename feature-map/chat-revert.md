# Revert chat file changes

A Revert changes icon appears immediately before Copy link on user and assistant
messages. It restores project files to their checkpoint before the related user
message, preserving all chat history. The owner reviews affected paths before
confirming, and can review/restore an automatic pre-revert backup using Undo
revert. Later message edits and manual edits are included in the restoration.

## Sub-features

- `capture`: idle top-level web-chat messages save private workspace checkpoints
  before dispatch, using the persisted web message's stable id.
- `review`: clicking Revert lists paths without changing project files.
- `restore`: confirmation restores files; a changed workspace requires a fresh
  review. The chat and Git metadata remain unchanged.
- `undo`: an automatic backup supports undoing the file restoration.
- `unavailable`: pending messages, active jobs/subagents, non-owner access,
  disconnected runtimes and messages without checkpoints cannot restore files.

## How to get to it (user POV)

- Hover/focus a user message, or use its visible action row on mobile. Choose
  Revert changes immediately before Copy link.
- Use the same action below an assistant response. This targets the checkpoint
  before its preceding user message.
- Review paths, Cancel or Restore files. After restoration choose Done, or Undo
  revert to review the saved backup before restoring it.

## Driving it with the repro environment

Preconditions: start the isolated verification environment described in
[Verify Omnigent](skills/verify-omnigent/SKILL.md). Use its mock provider.

`tests/e2e_ui/sessions/test_xwav_workbench.py::test_chat_file_revert_review_cancel_restore_and_undo`
sends a real web-chat message, edits project files, exercises review/cancel,
restores and undoes restoration, and checks that both user/assistant messages
remain. It runs at desktop and mobile widths. The native Codex variant
`test_native_codex_chat_file_revert` repeats this flow with a real Codex terminal
and a selected workspace distinct from the runner directory. Component tests cover both icon
placements, pending/running disablement, missing snapshots and navigation races.
Server/runtime tests cover permissions, idle guards, session isolation, file
modes, symlink safety, stale review tokens, corrupted blobs and partial-write
rollback.

## Gotchas

- Older messages and turns entered directly in an external terminal have no
  automatic web-chat checkpoint. A missing checkpoint is explicitly unavailable;
  the application never guesses file history.
- Messages submitted while work is already running do not get an idle checkpoint.
- Dependencies, Git metadata, virtual environments and runtime caches are excluded.
  A checkpoint is bounded to 100 MB and 10,000 entries. Oversized/unsupported
  workspaces cannot be reverted through this action.
- This restores workspace files, not external database records, external services, Git
  commits or model conversation context. The agent still sees the retained chat.
- Checkpoints live privately on the job's host. Replacing/deleting its sandbox
  removes that local history. Existing Linux runners receive the runtime through
  the authenticated shell resource; unsupported runtimes fail explicitly.

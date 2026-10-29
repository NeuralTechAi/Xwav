import { useContext, useEffect, useRef, useState } from "react";
import { QueryClientContext } from "@tanstack/react-query";
import { GitCommitHorizontalIcon, Layers2Icon, Loader2Icon } from "lucide-react";
import { MessageAction } from "@/components/ai-elements/message";
import { DisabledActionTooltip } from "@/components/DisabledActionTooltip";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useConversationEntryState } from "@/hooks/useConversationEntryState";
import { authenticatedFetch } from "@/lib/identity";
import { apiErrorFromResponse } from "@/lib/sessionsApi";
import type { Session } from "@/lib/types";

interface GitStatus {
  state: "ready" | "staged" | "committed" | "not_git";
  branch: string;
  repository: string;
  files: { path: string; staged: boolean; unstaged: boolean }[];
  count: number;
  staged_count: number;
  unstaged_count: number;
  token: string;
  commit?: string;
  author_required?: boolean;
}

export function GitMessageActions({
  sessionId,
  disabled = false,
}: {
  sessionId: string | null;
  disabled?: boolean;
}) {
  const queryClient = useContext(QueryClientContext);
  const session = queryClient?.getQueryData<Session>(["session", sessionId]);
  const live = useConversationEntryState(sessionId);
  const [action, setAction] = useState<"stage" | "commit" | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<GitStatus | null>(null);
  const [message, setMessage] = useState("");
  const [authorName, setAuthorName] = useState("");
  const [authorEmail, setAuthorEmail] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const generation = useRef(0);
  useEffect(() => {
    generation.current += 1;
    setAction(null);
    setStatus(null);
    setBusy(false);
    setError("");
    setMessage("");
    setAuthorName("");
    setAuthorEmail("");
    setDone(false);
    return () => {
      generation.current += 1;
    };
  }, [sessionId]);
  const reason =
    !sessionId || disabled
      ? "Wait until this message is saved"
      : session?.permissionLevel != null && session.permissionLevel < 4
        ? "Only the project owner can stage and commit files"
        : session?.parentSessionId
          ? "Stage and commit from the main project chat"
          : live.status === "streaming" || ["running", "waiting"].includes(live.sessionStatus)
            ? "Finish or stop this job before staging or committing"
            : "";

  async function request(operation: "status" | "stage" | "commit" | "init") {
    const response = await authenticatedFetch(
      `/v1/sessions/${encodeURIComponent(sessionId!)}/git-actions`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: operation,
          ...(operation === "commit" ? { message, token: status?.token } : {}),
          ...(operation === "commit" && status?.author_required
            ? { author_name: authorName, author_email: authorEmail }
            : {}),
        }),
      },
    );
    if (!response.ok) throw await apiErrorFromResponse(response);
    return response.json() as Promise<GitStatus>;
  }
  async function review(next: "stage" | "commit") {
    if (reason) return;
    const current = ++generation.current;
    setAction(next);
    setBusy(true);
    setError("");
    setStatus(null);
    setDone(false);
    try {
      const result = await request("status");
      if (generation.current === current) setStatus(result);
    } catch (failure) {
      if (generation.current === current)
        setError(failure instanceof Error ? failure.message : "Git status unavailable");
    } finally {
      if (generation.current === current) setBusy(false);
    }
  }
  async function initialize() {
    if (busy || reason) return;
    const current = ++generation.current;
    setBusy(true);
    setError("");
    try {
      const result = await request("init");
      if (generation.current === current) setStatus(result);
    } catch (failure) {
      if (generation.current === current)
        setError(failure instanceof Error ? failure.message : "Could not initialize Git");
    } finally {
      if (generation.current === current) setBusy(false);
    }
  }
  async function apply() {
    if (!action || !status || busy || done || reason) return;
    const current = ++generation.current;
    setBusy(true);
    setError("");
    try {
      const result = await request(action);
      if (generation.current !== current) return;
      setStatus(result);
      setDone(true);
      void queryClient?.invalidateQueries({
        predicate: (query) => query.queryKey[1] === sessionId,
      });
    } catch (failure) {
      if (generation.current === current) {
        setError(failure instanceof Error ? failure.message : "Git action failed");
        setStatus(null);
      }
    } finally {
      if (generation.current === current) setBusy(false);
    }
  }
  const files =
    status?.files.filter((file) => (action === "commit" ? file.staged : file.unstaged)) ?? [];
  const count = (action === "commit" ? status?.staged_count : status?.unstaged_count) ?? 0;
  return (
    <>
      <DisabledActionTooltip reason={reason || undefined} label="Stage changes">
        <MessageAction
          label="Stage changes"
          tooltip={reason ? undefined : "Review and stage project changes for a Git commit"}
          size="icon-xxs"
          disabled={!!reason}
          onClick={() => void review("stage")}
        >
          <Layers2Icon size={14} />
        </MessageAction>
      </DisabledActionTooltip>
      <DisabledActionTooltip reason={reason || undefined} label="Commit changes">
        <MessageAction
          label="Commit changes"
          tooltip={reason ? undefined : "Review staged files and create a Git commit"}
          size="icon-xxs"
          disabled={!!reason}
          onClick={() => void review("commit")}
        >
          <GitCommitHorizontalIcon size={14} />
        </MessageAction>
      </DisabledActionTooltip>
      <Dialog
        open={action !== null}
        onOpenChange={(open) => {
          if (!open && !busy) {
            generation.current += 1;
            setAction(null);
          }
        }}
      >
        <DialogContent
          aria-describedby="chat-git-description"
          className="max-h-[calc(100dvh-2rem)] overflow-y-auto overscroll-contain [overflow-wrap:anywhere] sm:max-w-lg"
        >
          <DialogHeader>
            <DialogTitle>
              {action === "stage" ? "Stage project changes" : "Commit staged changes"}
            </DialogTitle>
          </DialogHeader>
          <p id="chat-git-description" className="text-sm text-muted-foreground">
            {action === "stage"
              ? "Stage all current project changes, including new and deleted files. Git-ignored files stay excluded."
              : "Create a local commit from the staged versions of these files. Unstaged edits stay outside this commit."}{" "}
            These actions use the current project, regardless of which message you clicked. Push
            separately to publish commits to GitHub.
          </p>
          {busy && (
            <p role="status" className="flex items-center gap-2 text-sm">
              <Loader2Icon className="size-4 animate-spin" />
              {status ? "Updating Git…" : "Checking Git status…"}
            </p>
          )}
          {error && (
            <p role="alert" className="whitespace-pre-wrap break-words text-sm text-destructive">
              {error}
            </p>
          )}
          {status?.state === "not_git" && (
            <div className="space-y-3 text-sm">
              <p>
                This project has no Git repository. Initialize one locally to stage and commit.
                Local dependency folders and .env files will be excluded by default. Connecting a
                GitHub remote and pushing remain separate steps.
              </p>
              <Button
                className="h-auto min-h-8 max-w-full whitespace-normal py-1.5"
                disabled={busy || !!reason}
                onClick={() => void initialize()}
              >
                Initialize Git repository
              </Button>
            </div>
          )}
          {status && status.state !== "not_git" && !done && (
            <div className="space-y-2 text-sm">
              <p className="break-all">Branch: {status.branch}</p>
              <p>
                {count} {action === "commit" ? "staged" : "unstaged"} files
              </p>
              <ul className="max-h-56 overflow-auto rounded-md border p-3 font-mono text-xs">
                {files.map((file) => (
                  <li key={file.path} className="break-all py-1">
                    {file.path}
                  </li>
                ))}
              </ul>
              {count > files.length && (
                <p>
                  Showing {files.length} of {count} files. This action includes all {count} files.
                </p>
              )}
              {action === "commit" && (
                <div className="space-y-2">
                  <label htmlFor="chat-git-message">Commit message</label>
                  <Input
                    id="chat-git-message"
                    value={message}
                    maxLength={4000}
                    onChange={(event) => setMessage(event.target.value)}
                    placeholder="Describe what changed"
                    disabled={busy}
                  />
                </div>
              )}
              {action === "commit" && status.author_required && (
                <div className="space-y-2">
                  <p>Git needs an author identity. These details apply to this commit only.</p>
                  <label htmlFor="chat-git-author">Author name</label>
                  <Input
                    id="chat-git-author"
                    value={authorName}
                    maxLength={200}
                    onChange={(event) => setAuthorName(event.target.value)}
                    disabled={busy}
                  />
                  <label htmlFor="chat-git-email">Author email</label>
                  <Input
                    id="chat-git-email"
                    type="email"
                    value={authorEmail}
                    maxLength={200}
                    onChange={(event) => setAuthorEmail(event.target.value)}
                    disabled={busy}
                  />
                </div>
              )}
            </div>
          )}
          {done && (
            <p role="status" className="text-sm">
              {status?.state === "committed"
                ? `Commit created: ${status.commit?.slice(0, 12)}. Push it to update GitHub.`
                : "Project changes staged. Click Commit to create a commit."}
            </p>
          )}
          <DialogFooter className="mx-0 mb-0 min-w-0 p-0 pt-2 sm:flex-wrap [&>button]:h-auto [&>button]:min-h-8 [&>button]:min-w-0 [&>button]:max-w-full [&>button]:whitespace-normal [&>button]:py-1.5">
            <Button variant="outline" disabled={busy} onClick={() => setAction(null)}>
              {done ? "Done" : "Cancel"}
            </Button>
            {!busy && action && (
              <Button variant="outline" onClick={() => void review(action)}>
                Refresh files
              </Button>
            )}
            {!done && (
              <Button
                disabled={
                  busy ||
                  !!reason ||
                  !status ||
                  count === 0 ||
                  (action === "commit" && !message.trim()) ||
                  (action === "commit" &&
                    status?.author_required &&
                    (!authorName.trim() || !/\S+@\S+/.test(authorEmail)))
                }
                onClick={() => void apply()}
              >
                {action === "stage" ? "Stage all changes" : "Create commit"}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

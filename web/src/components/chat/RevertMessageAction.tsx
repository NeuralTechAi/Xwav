import { useContext, useEffect, useRef, useState } from "react";
import { QueryClientContext } from "@tanstack/react-query";
import { Loader2Icon, Undo2Icon } from "lucide-react";
import { DisabledActionTooltip } from "@/components/DisabledActionTooltip";
import { MessageAction } from "@/components/ai-elements/message";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useConversationEntryState } from "@/hooks/useConversationEntryState";
import { authenticatedFetch } from "@/lib/identity";
import { apiErrorFromResponse } from "@/lib/sessionsApi";
import type { Session } from "@/lib/types";

interface RevertResult {
  state: "ready" | "restored";
  token?: string;
  changes?: { path: string; action: string }[];
  count: number;
  backup_id?: string;
}

export function RevertMessageAction({
  sessionId,
  itemId,
  disabled = false,
}: {
  sessionId: string | null;
  itemId: string | null;
  disabled?: boolean;
}) {
  const queryClient = useContext(QueryClientContext);
  const session = queryClient?.getQueryData<Session>(["session", sessionId]);
  const live = useConversationEntryState(sessionId);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [plan, setPlan] = useState<RevertResult | null>(null);
  const [restored, setRestored] = useState<RevertResult | null>(null);
  const [backup, setBackup] = useState<string | null>(null);
  const generation = useRef(0);
  useEffect(() => {
    generation.current += 1;
    setOpen(false);
    setPlan(null);
    setRestored(null);
    setBackup(null);
    setBusy(false);
    setError("");
    return () => {
      generation.current += 1;
    };
  }, [sessionId, itemId]);
  const running =
    live.status === "streaming" || ["running", "waiting"].includes(live.sessionStatus);
  const reason =
    !sessionId || !itemId || disabled
      ? "Wait until this message is saved"
      : session?.permissionLevel != null && session.permissionLevel < 4
        ? "Only the project owner can revert files"
        : session?.parentSessionId
          ? "Revert files from the main project chat"
          : running
            ? "Finish or stop this job before reverting files"
            : "";
  async function request(action: "plan" | "apply", backupId: string | null, token?: string) {
    const response = await authenticatedFetch(
      `/v1/sessions/${encodeURIComponent(sessionId!)}/revert`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          ...(backupId ? { backup_id: backupId } : { item_id: itemId }),
          token,
        }),
      },
    );
    if (!response.ok) throw await apiErrorFromResponse(response);
    return response.json() as Promise<RevertResult>;
  }
  async function review(backupId: string | null = null) {
    const current = ++generation.current;
    setOpen(true);
    setBusy(true);
    setError("");
    setPlan(null);
    setRestored(null);
    setBackup(backupId);
    try {
      const result = await request("plan", backupId);
      if (generation.current === current) setPlan(result);
    } catch (failure) {
      if (generation.current === current)
        setError(failure instanceof Error ? failure.message : "Could not review these files");
    } finally {
      if (generation.current === current) setBusy(false);
    }
  }
  async function apply() {
    if (!plan?.token || reason) return;
    const current = ++generation.current;
    setBusy(true);
    setError("");
    try {
      const result = await request("apply", backup, plan.token);
      if (generation.current !== current) return;
      setRestored(result);
      setPlan(null);
      void queryClient?.invalidateQueries({
        predicate: (query) => query.queryKey[1] === sessionId,
      });
    } catch (failure) {
      if (generation.current === current) {
        setError(failure instanceof Error ? failure.message : "Files could not be restored");
        setPlan(null);
      }
    } finally {
      if (generation.current === current) setBusy(false);
    }
  }
  return (
    <>
      <DisabledActionTooltip reason={reason || undefined} label="Revert changes">
        <MessageAction
          tooltip={reason ? undefined : "Revert changes"}
          label="Revert changes"
          size="icon-xxs"
          data-testid="revert-message"
          disabled={!!reason}
          onClick={() => void review()}
        >
          <Undo2Icon size={14} />
        </MessageAction>
      </DisabledActionTooltip>
      <Dialog
        open={open}
        onOpenChange={(value) => {
          if (!busy) setOpen(value);
        }}
      >
        <DialogContent aria-describedby="revert-files-description">
          <DialogHeader>
            <DialogTitle>{backup ? "Undo file revert" : "Revert project changes?"}</DialogTitle>
          </DialogHeader>
          <p id="revert-files-description" className="text-sm text-muted-foreground">
            {backup
              ? "Restore the files saved just before your last revert."
              : "Restore project files to before this message, including changes from later messages and manual edits."}{" "}
            Chat history stays. Git history and installed dependencies stay.
          </p>
          {busy && (
            <p role="status" className="flex items-center gap-2 text-sm">
              <Loader2Icon className="size-4 animate-spin" />
              Checking project files…
            </p>
          )}
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          {plan && (
            <div className="space-y-2 text-sm">
              <p>
                {plan.count === 0
                  ? "No file changes to revert."
                  : `${plan.count} paths will change. A backup will be saved first.`}
              </p>
              <ul className="max-h-56 overflow-auto rounded-md border p-3 font-mono text-xs">
                {plan.changes?.map((change) => (
                  <li key={change.path} className="break-all py-1">
                    {change.action === "remove" ? "Remove" : "Restore"} · {change.path}
                  </li>
                ))}
              </ul>
              {plan.count > (plan.changes?.length ?? 0) && (
                <p>Showing the first {plan.changes?.length} paths.</p>
              )}
            </div>
          )}
          {restored && (
            <p role="status" className="text-sm">
              Project files restored. Your chat history is unchanged.
            </p>
          )}
          <DialogFooter>
            <Button variant="outline" disabled={busy} onClick={() => setOpen(false)}>
              {restored ? "Done" : "Cancel"}
            </Button>
            {error && (
              <Button variant="outline" onClick={() => void review(backup)}>
                Review again
              </Button>
            )}
            {restored?.backup_id && (
              <Button variant="outline" onClick={() => void review(restored.backup_id)}>
                Undo revert
              </Button>
            )}
            {plan && (
              <Button disabled={busy || !!reason || plan.count === 0} onClick={() => void apply()}>
                Restore files
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

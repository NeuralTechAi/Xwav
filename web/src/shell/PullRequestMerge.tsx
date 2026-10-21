// The Summary tab's Merge button: its state follows GitHub's mergeStateStatus and
// auto-merge, and a click opens a confirmation where the merge method can change.

import { useRef, useState } from "react";
import { GitMergeIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import {
  useDisablePullRequestAutoMerge,
  useMergePullRequest,
  usePullRequestMergeOptions,
  type PullRequest,
  type PullRequestMergeMethod,
} from "@/hooks/usePullRequests";

/** Picker entries, as GitHub's merge menu names them. */
const MERGE_METHOD_LABELS: Record<PullRequestMergeMethod, string> = {
  merge: "Create a merge commit",
  squash: "Squash and merge",
  rebase: "Rebase and merge",
};

/** Button labels for each method, as on GitHub's merge button. */
export const MERGE_BUTTON_LABELS: Record<PullRequestMergeMethod, string> = {
  merge: "Merge pull request",
  squash: "Squash and merge",
  rebase: "Rebase and merge",
};

/** GitHub's green merge button. */
const MERGE_BUTTON_CLASS =
  "bg-green-600 text-white hover:bg-green-700 dark:bg-green-600 dark:hover:bg-green-500";

/** Why GitHub won't merge the PR yet, by mergeStateStatus. */
const BLOCKED_HINTS: Record<string, string> = {
  BLOCKED: "Required checks or reviews haven’t passed.",
  BEHIND: "Update the branch first.",
  DIRTY: "Resolve conflicts first.",
  DRAFT: "Mark the pull request ready for review first.",
  UNSTABLE: "Some checks aren’t passing.",
};

export type MergeButtonState =
  | { kind: "auto_merge" }
  | { kind: "checking"; hint: string }
  | { kind: "blocked"; hint: string }
  | { kind: "ready"; headSha: string };

/** What the Merge button shows for a PR, from its auto-merge and merge state. */
export function mergeButtonState(
  pr: Pick<PullRequest, "auto_merge" | "merge_state_status" | "head_sha">,
): MergeButtonState {
  if (pr.auto_merge) return { kind: "auto_merge" };
  const status = pr.merge_state_status;
  if (status === "CLEAN" && pr.head_sha) return { kind: "ready", headSha: pr.head_sha };
  // GitHub computes the state after a push; the next poll usually has it.
  if (!status || status === "UNKNOWN" || status === "CLEAN") {
    return { kind: "checking", hint: "Checking whether it can merge…" };
  }
  return {
    kind: "blocked",
    hint: BLOCKED_HINTS[status] ?? "GitHub reports that it can’t merge yet.",
  };
}

/** Confirms the merge and picks its method; the head is fixed when the dialog opens. */
function PullRequestMergeDialog({
  conversationId,
  prUrl,
  pr,
  headSha,
  onClose,
  onMerged,
}: {
  conversationId: string;
  prUrl: string;
  pr: PullRequest;
  headSha: string;
  onClose: () => void;
  onMerged: () => void;
}) {
  const options = usePullRequestMergeOptions(conversationId, prUrl, true);
  const merge = useMergePullRequest(conversationId);
  const [chosen, setChosen] = useState<PullRequestMergeMethod | null>(null);
  const methods = options.data?.methods ?? [];
  const method = chosen && methods.includes(chosen) ? chosen : (options.data?.default ?? null);

  // `isPending` updates after a render, so a fast second click needs this guard.
  const submitting = useRef(false);
  const confirm = () => {
    if (!method || submitting.current) return;
    submitting.current = true;
    merge.mutate(
      { prUrl, mergeMethod: method, expectedHead: headSha },
      {
        onSuccess: () => {
          onMerged();
          onClose();
        },
        onSettled: () => {
          submitting.current = false;
        },
      },
    );
  };

  return (
    <Dialog
      open
      // Keep the dialog up while a merge is in flight so its outcome stays visible.
      onOpenChange={(next) => !next && !merge.isPending && onClose()}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Merge pull request #{pr.number}?</DialogTitle>
          <DialogDescription>
            {pr.title} will be merged into{" "}
            <span className="font-mono text-foreground">{pr.base_ref ?? "its base branch"}</span>.
            This can’t be undone.
          </DialogDescription>
        </DialogHeader>
        {options.isPending ? (
          <p role="status" className="text-ui text-muted-foreground">
            Loading merge methods…
          </p>
        ) : options.isError ? (
          <p role="alert" className="text-ui text-destructive">
            {options.error.message}
          </p>
        ) : methods.length === 0 ? (
          <p role="alert" className="text-ui text-destructive">
            This repository allows no merge method.
          </p>
        ) : (
          <Select
            value={method ?? undefined}
            onValueChange={(value) => setChosen(value as PullRequestMergeMethod)}
            disabled={merge.isPending}
          >
            <SelectTrigger aria-label="Merge method" className="h-8 w-full text-ui">
              <SelectValue placeholder="Merge method" />
            </SelectTrigger>
            <SelectContent>
              {methods.map((value) => (
                <SelectItem key={value} value={value}>
                  {MERGE_METHOD_LABELS[value]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        {merge.isError && (
          <p role="alert" className="text-ui text-destructive">
            {merge.error.message}
          </p>
        )}
        <DialogFooter>
          <Button variant="outline" disabled={merge.isPending} onClick={onClose}>
            Cancel
          </Button>
          <Button
            className={MERGE_BUTTON_CLASS}
            disabled={!method || merge.isPending}
            onClick={confirm}
          >
            {merge.isPending && <Spinner aria-hidden />}
            {merge.isPending
              ? "Merging…"
              : method
                ? MERGE_BUTTON_LABELS[method]
                : "Merge pull request"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Auto-merge is on: say so, and let the user turn it off. */
function PullRequestAutoMerge({
  conversationId,
  prUrl,
  pr,
}: {
  conversationId: string;
  prUrl: string;
  pr: PullRequest;
}) {
  const disable = useDisablePullRequestAutoMerge(conversationId);
  // The auto-merge GitHub turned off; it shows as on here until the refetch lands.
  const [disabledAt, setDisabledAt] = useState<string | null>(null);
  const enabledAt = pr.auto_merge?.enabled_at ?? "";
  const busy = disable.isPending || disabledAt === enabledAt;
  // `isPending` updates after a render, so a fast second click needs this guard.
  const submitting = useRef(false);
  const disableAutoMerge = () => {
    if (busy || submitting.current) return;
    submitting.current = true;
    disable.mutate(prUrl, {
      onSuccess: () => setDisabledAt(enabledAt),
      onSettled: () => {
        submitting.current = false;
      },
    });
  };
  return (
    <>
      <Button size="sm" variant="outline" disabled={busy} onClick={disableAutoMerge}>
        {busy && <Spinner aria-hidden />}
        Disable auto-merge
      </Button>
      <span className="text-ui text-muted-foreground">
        This pull request will <strong className="text-foreground">merge automatically</strong> when
        all requirements are met.
      </span>
      {disable.isError && (
        <p role="alert" className="w-full text-ui text-destructive">
          {disable.error.message}
        </p>
      )}
    </>
  );
}

export function PullRequestMerge({
  conversationId,
  prUrl,
  pr,
}: {
  conversationId: string;
  prUrl: string;
  pr: PullRequest;
}) {
  // The repository's default method names the button, so it loads with the button.
  const options = usePullRequestMergeOptions(conversationId, prUrl, !pr.auto_merge);
  // The head the user confirms, kept while the dialog is open even if a poll moves it.
  const [confirmingHead, setConfirmingHead] = useState<string | null>(null);
  // GitHub accepted a merge of this head; the PR stays open here until the refetch lands.
  const [mergedHead, setMergedHead] = useState<string | null>(null);

  if (pr.auto_merge) {
    return (
      <section className="flex flex-wrap items-center gap-2" aria-label="Merge">
        <PullRequestAutoMerge conversationId={conversationId} prUrl={prUrl} pr={pr} />
      </section>
    );
  }
  const state: MergeButtonState =
    mergedHead && mergedHead === pr.head_sha
      ? { kind: "checking", hint: "Merge requested. Refreshing…" }
      : mergeButtonState(pr);
  const defaultMethod = options.data?.default;
  const label = defaultMethod ? MERGE_BUTTON_LABELS[defaultMethod] : "Merge pull request";
  return (
    <section className="flex flex-wrap items-center gap-2" aria-label="Merge">
      <Button
        size="sm"
        variant={state.kind === "ready" ? "default" : "outline"}
        className={cn(state.kind === "ready" && MERGE_BUTTON_CLASS)}
        disabled={state.kind !== "ready"}
        onClick={() => state.kind === "ready" && setConfirmingHead(state.headSha)}
      >
        {state.kind === "checking" ? <Spinner aria-hidden /> : <GitMergeIcon aria-hidden />}
        {label}
      </Button>
      {"hint" in state && <span className="text-ui text-muted-foreground">{state.hint}</span>}
      {confirmingHead && (
        <PullRequestMergeDialog
          conversationId={conversationId}
          prUrl={prUrl}
          pr={pr}
          headSha={confirmingHead}
          onMerged={() => setMergedHead(confirmingHead)}
          onClose={() => setConfirmingHead(null)}
        />
      )}
    </section>
  );
}

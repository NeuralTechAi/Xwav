import { useContext, useEffect, useRef, useState } from "react";
import { QueryClientContext, useQuery } from "@tanstack/react-query";
import { ChevronDownIcon, FileDiffIcon, RefreshCwIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { authenticatedFetch } from "@/lib/identity";
import { apiErrorFromResponse } from "@/lib/sessionsApi";

interface ChangedFile {
  path: string;
  status: "added" | "deleted" | "modified";
  additions: number | null;
  deletions: number | null;
  diff?: string;
  note?: string;
  truncated?: boolean;
}
interface Changes {
  count: number;
  files: ChangedFile[];
  scope: "next_request" | "current_workspace";
}

async function fetchChanges(
  sessionId: string,
  itemId: string,
  path?: string,
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({ item_id: itemId });
  if (path !== undefined) params.set("path", path);
  const response = await authenticatedFetch(
    `/v1/sessions/${encodeURIComponent(sessionId)}/changes?${params}`,
    { signal },
  );
  if (!response.ok) throw await apiErrorFromResponse(response);
  return response.json() as Promise<Changes>;
}

export function ChatChangeSummary(props: { sessionId: string; itemId: string; running: boolean }) {
  const client = useContext(QueryClientContext);
  return client ? <ChangeSummary {...props} /> : null;
}

function ChangeSummary({
  sessionId,
  itemId,
  running,
}: {
  sessionId: string;
  itemId: string;
  running: boolean;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  useEffect(() => {
    setSelected(null);
    setVisible(false);
    const element = container.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "200px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [sessionId, itemId]);
  const summary = useQuery({
    queryKey: ["chat-changes", sessionId, itemId],
    queryFn: ({ signal }) => fetchChanges(sessionId, itemId, undefined, signal),
    enabled: visible && !running,
    retry: false,
    refetchOnWindowFocus: false,
  });
  const detail = useQuery({
    queryKey: ["chat-change-diff", sessionId, itemId, selected, summary.dataUpdatedAt],
    queryFn: ({ signal }) => fetchChanges(sessionId, itemId, selected!, signal),
    enabled: selected !== null && !running,
    retry: false,
    refetchOnWindowFocus: false,
  });
  const data = summary.data;
  const file = detail.data?.files[0];
  const additions = data?.files.reduce((sum, row) => sum + (row.additions ?? 0), 0) ?? 0;
  const deletions = data?.files.reduce((sum, row) => sum + (row.deletions ?? 0), 0) ?? 0;
  const incompleteStats =
    data?.files.some((row) => row.additions === null) || (data && data.count > data.files.length);
  return (
    <div
      ref={container}
      className="my-3 w-full min-w-0 rounded-lg border bg-muted/20 text-sm"
      data-testid="chat-change-summary"
    >
      <div className="flex items-center gap-2 px-3 py-2">
        <button
          type="button"
          className="flex min-w-0 flex-1 items-center gap-2 text-left font-medium"
          aria-expanded={expanded}
          onClick={() => setExpanded((value) => !value)}
        >
          <FileDiffIcon className="size-4 shrink-0" aria-hidden />
          <span>
            {data ? `${data.count} file${data.count === 1 ? "" : "s"} changed` : "Changes"}
          </span>
          {data && (
            <span className="ml-auto whitespace-nowrap font-mono text-xs">
              <span className="text-green-600 dark:text-green-400">+{additions}</span>{" "}
              <span className="text-red-600 dark:text-red-400">−{deletions}</span>
              {incompleteStats ? " (partial)" : ""}
            </span>
          )}
          <ChevronDownIcon
            className={`size-3 shrink-0 ${expanded ? "" : "-rotate-90"}`}
            aria-hidden
          />
        </button>
        <Button
          variant="ghost"
          size="icon-xxs"
          aria-label="Refresh changes"
          title="Refresh changes"
          disabled={running || summary.isFetching}
          onClick={() => void summary.refetch()}
        >
          <RefreshCwIcon className={`size-3 ${summary.isFetching ? "animate-spin" : ""}`} />
        </Button>
      </div>
      {expanded && (
        <div className="border-t px-3 py-2">
          {running ? (
            <p className="text-xs text-muted-foreground">
              Changes will be available when the job stops.
            </p>
          ) : summary.isPending ? (
            <p role="status" className="text-xs text-muted-foreground">
              Checking file changes…
            </p>
          ) : summary.isError ? (
            <p className="text-xs text-muted-foreground">{summary.error.message}</p>
          ) : (
            data && (
              <>
                <p className="mb-2 text-xs text-muted-foreground">
                  {data.scope === "next_request"
                    ? "From this request to the next request."
                    : "From this request to the current workspace."}{" "}
                  Includes manual edits.
                </p>
                {data.count === 0 && <p className="text-xs">No file changes.</p>}
                <ul className="max-h-64 overflow-auto">
                  {data.files.map((row) => (
                    <li key={row.path}>
                      <button
                        type="button"
                        className="flex w-full items-center gap-2 rounded px-1 py-1.5 text-left hover:bg-muted focus-visible:outline focus-visible:outline-ring"
                        title={`View changes to ${row.path}`}
                        onClick={() => setSelected(row.path)}
                      >
                        <span className="w-4 shrink-0 font-mono text-xs" aria-label={row.status}>
                          {row.status === "added" ? "A" : row.status === "deleted" ? "D" : "M"}
                        </span>
                        <span className="min-w-0 flex-1 break-all font-mono text-xs">
                          {row.path}
                        </span>
                        {row.additions !== null && (
                          <span className="shrink-0 font-mono text-xs">
                            <span className="text-green-600 dark:text-green-400">
                              +{row.additions}
                            </span>{" "}
                            <span className="text-red-600 dark:text-red-400">−{row.deletions}</span>
                          </span>
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
                {data.count > data.files.length && (
                  <p className="text-xs text-muted-foreground">
                    Showing the first {data.files.length} files of {data.count}.
                  </p>
                )}
              </>
            )
          )}
        </div>
      )}
      <Dialog
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <DialogContent
          className="flex max-h-[85dvh] w-[95vw] max-w-5xl flex-col overflow-hidden"
          aria-describedby="chat-diff-description"
        >
          <DialogHeader>
            <DialogTitle className="break-all pr-6 font-mono text-sm">{selected}</DialogTitle>
          </DialogHeader>
          <p id="chat-diff-description" className="text-xs text-muted-foreground">
            File changes for this request. Lines beginning with + were added; − were removed.
          </p>
          {detail.isPending && <p role="status">Loading diff…</p>}
          {detail.isError && <p role="alert">{detail.error.message}</p>}
          {file?.note && <p>{file.note}</p>}
          {file?.truncated && <p>Diff truncated for this large change.</p>}
          {file?.diff && (
            <pre
              aria-label="Code changes"
              className="min-h-0 overflow-auto rounded border bg-background p-3 font-mono text-xs leading-5"
            >
              {file.diff.split("\n").map((line, index) => (
                <span
                  // eslint-disable-next-line react/no-array-index-key -- Immutable diff lines have no child state; duplicate lines need positional keys.
                  key={`${index}:${line}`}
                  className={`block min-w-max ${line.startsWith("+") ? "bg-green-500/10 text-green-700 dark:text-green-300" : line.startsWith("-") ? "bg-red-500/10 text-red-700 dark:text-red-300" : ""}`}
                >
                  {line || " "}
                </span>
              ))}
            </pre>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

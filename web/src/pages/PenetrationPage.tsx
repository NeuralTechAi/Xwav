import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ScanLineIcon, DownloadIcon, RefreshCwIcon } from "lucide-react";
import { Link, useSearchParams } from "@/lib/routing";
import { useProjectSessions } from "@/hooks/useConversations";
import { authenticatedFetch } from "@/lib/identity";
import { apiErrorFromResponse } from "@/lib/sessionsApi";
import { PageScroll } from "@/components/PageScroll";
import { reportDownload } from "./PreproductionPage";
import "./preproduction.css";
import { FixDashboardIssues } from "@/components/chat/FixDashboardIssues";

interface Finding {
  id: string;
  title: string;
  severity: string;
  validation: string;
  description: string;
  impact: string;
  target: string;
  evidence: string;
  technical_analysis: string;
  poc_description: string;
  remediation_steps: string;
}
interface StrixReport {
  state: string;
  runs: { id: string; updated_at: number }[];
  run?: {
    id: string;
    started_at: string;
    finished_at: string;
    summary: string;
    recommendations: string;
    mode: string;
  };
  findings: Finding[];
  total_findings?: number;
  counts?: Record<string, number>;
  warnings?: string[];
  notice?: string;
  strix_installed?: boolean;
  error?: string;
  phase?: string;
  managed?: boolean;
}
const severities = ["critical", "high", "medium", "low", "info", "unknown"];
const states: Record<string, string> = {
  empty: "No Strix reports yet",
  running: "Scan in progress",
  complete: "Scan completed",
  stopped: "Scan stopped",
  unknown: "Scan status unavailable",
  error: "Scan could not complete",
};
export function PenetrationPage() {
  const [params] = useSearchParams();
  const requested = params.get("session"),
    project = params.get("project") ?? "";
  const jobs = useProjectSessions(project, !requested && !!project);
  const session = requested ?? (project ? (jobs.data?.pages[0]?.data[0]?.id ?? null) : null);
  const [selection, setSelection] = useState({ session, run: params.get("run") ?? "" });
  const run = selection.session === session ? selection.run : "";
  const [severity, setSeverity] = useState("all");
  const started = useRef(new Set<string>());
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  async function requestAction(action: string) {
    if (!session || busy) return;
    setBusy(true);
    setActionError("");
    try {
      const response = await authenticatedFetch(
        `/v1/sessions/${encodeURIComponent(session)}/penetration`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action }),
        },
      );
      if (!response.ok) throw await apiErrorFromResponse(response);
      const result = await response.json();
      setSelection({ session, run: "" });
      client.setQueryData(["penetration", session, ""], result);
    } catch (failure) {
      setActionError(failure instanceof Error ? failure.message : "Could not start scan");
    } finally {
      setBusy(false);
    }
  }
  const query = useQuery({
    queryKey: ["penetration", session, run],
    enabled: !!session,
    retry: false,
    queryFn: async ({ signal }) => {
      const reportParams = new URLSearchParams();
      if (run) reportParams.set("run", run);
      const autoStart = !run && !started.current.has(session!);
      if (autoStart) started.current.add(session!);
      const response = await authenticatedFetch(
        `/v1/sessions/${encodeURIComponent(session!)}/penetration${reportParams.size ? `?${reportParams}` : ""}`,
        autoStart
          ? {
              signal,
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ action: "start" }),
            }
          : { signal },
      );
      if (!response.ok) throw await apiErrorFromResponse(response);
      return response.json() as Promise<StrixReport>;
    },
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
  });
  const report = query.data;
  const findings = report?.findings ?? [];
  function download(format: "json" | "html" | "csv") {
    if (!report) return;
    const exported = {
      ...report,
      id: report.run?.id,
      checks: findings.map((finding) => ({
        id: finding.id,
        name: finding.title,
        category: finding.severity,
        platform: "shared",
        status: finding.validation,
        output: [
          finding.description,
          finding.impact,
          finding.target,
          finding.technical_analysis,
          finding.evidence,
          finding.poc_description,
          finding.remediation_steps,
        ]
          .filter(Boolean)
          .join("\n\n"),
      })),
    };
    const blob = new Blob([reportDownload(exported, format, "Xwav Penetration Test — Strix")], {
      type: format === "json" ? "application/json" : format === "csv" ? "text/csv" : "text/html",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `xwav-strix-report.${format}`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <PageScroll
      className="preproduction-page"
      maxWidthClassName="max-w-6xl"
      contentClassName="py-8"
    >
      <header className="preproduction-heading">
        <div>
          <p className="preproduction-eyebrow">
            <ScanLineIcon size={16} /> XWAV SECURITY LAB
          </p>
          <h1>Penetration Test</h1>
          <p>Strix findings, evidence and remediation for this job.</p>
        </div>
        <div className="preproduction-actions">
          <FixDashboardIssues
            key={`${session}:${report?.run?.id}`}
            sessionId={session}
            kind="penetration"
            runId={report?.run?.id}
            disabled={!report || report.state === "running"}
          />
          <Link to={session ? `/c/${encodeURIComponent(session)}` : "/"}>Back to job</Link>
          <button
            type="button"
            disabled={
              !session || busy || (!run && report?.managed === true && report.state === "running")
            }
            onClick={() => void requestAction("start")}
          >
            <RefreshCwIcon size={15} className={busy ? "animate-spin" : ""} /> Run again
          </button>
          {!run && report?.managed === true && report.state === "running" && (
            <button type="button" disabled={busy} onClick={() => void requestAction("cancel")}>
              Stop scan
            </button>
          )}
        </div>
      </header>
      {!session && (
        <p role="status">
          Open Penetration Test from a job, or create a job in this project first.
        </p>
      )}
      {session && query.isPending && <p role="status">Starting full-project Strix scan…</p>}
      {actionError && <p role="alert">{actionError}</p>}
      {query.isError && <p role="alert">{query.error.message}</p>}
      {report?.error && <p role="alert">{report.error}</p>}
      {report && (
        <>
          <section className="preproduction-run" aria-label="Strix scan status">
            <div>
              <strong>{states[report.state] ?? "Scan status unavailable"}</strong>
              <p>
                {report.run?.id ?? "Run the native Strix skill in this job to create a report."}
              </p>
              {report.phase && <p role="status">{report.phase}</p>}
              {report.run?.started_at && (
                <p>
                  Started: {report.run.started_at}
                  {report.run.finished_at ? ` · Finished: ${report.run.finished_at}` : ""}
                </p>
              )}
            </div>
            {report.run?.mode && <span>Mode: {report.run.mode}</span>}
          </section>
          <section
            className="my-4 grid grid-cols-2 gap-3 sm:grid-cols-3"
            aria-label="Finding severity totals"
          >
            {severities.map((level) => (
              <div key={level} className="rounded-xl border bg-card p-4">
                <p className="text-xs capitalize text-muted-foreground">
                  {level === "info" ? "Informational" : level}
                </p>
                <p
                  className={`mt-2 text-3xl font-semibold ${["critical", "high"].includes(level) ? "text-destructive" : ""}`}
                >
                  {report.counts?.[level] ?? 0}
                </p>
              </div>
            ))}
          </section>
          <p className="preproduction-notice">
            {report.notice ?? "No security pass is implied by an empty or missing report."}
          </p>
          <section
            className="my-4 rounded-xl border bg-card p-4 text-sm leading-6"
            aria-label="Run with native Strix skill"
          >
            <h2 className="font-semibold">Automatic full-project scan</h2>
            <p>
              Opening this page starts Strix against a disposable snapshot of the entire project,
              including saved, uncommitted files. Runtime setup is cached after its first use. Scans
              use the configured zero-cost model pool, full-project scope and bounded execution. Run
              again creates a fresh snapshot and scan; live results update automatically.
            </p>
            {report.strix_installed === false && !report.managed && (
              <p className="mt-2 text-muted-foreground">
                The optional Strix CLI is not installed in this job. The skill can guide setup;
                saved reports remain viewable.
              </p>
            )}
          </section>
          {report.warnings?.map((warning) => (
            <p key={warning} className="my-2 text-sm" role="status">
              {warning}
            </p>
          ))}
          {!!report.runs.length && (
            <div className="preproduction-toolbar my-4">
              <label>
                Scan{" "}
                <select
                  aria-label="Strix scan"
                  value={run}
                  onChange={(event) => setSelection({ session, run: event.target.value })}
                >
                  <option value="">Latest scan</option>
                  {report.runs.map((row) => (
                    <option key={row.id} value={row.id}>
                      {row.id}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Severity{" "}
                <select
                  aria-label="Finding severity"
                  value={severity}
                  onChange={(event) => setSeverity(event.target.value)}
                >
                  <option value="all">All severities</option>
                  {severities.map((level) => (
                    <option key={level} value={level}>
                      {level}
                    </option>
                  ))}
                </select>
              </label>
              {(["json", "html", "csv"] as const).map((format) => (
                <button type="button" key={format} onClick={() => download(format)}>
                  <DownloadIcon size={14} /> Download {format.toUpperCase()}
                </button>
              ))}
            </div>
          )}
          {report.run?.summary && (
            <section className="my-4 rounded-xl border p-4">
              <h2 className="font-semibold">Scan summary</h2>
              <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6">
                {report.run.summary}
              </p>
            </section>
          )}
          {report.state !== "empty" && findings.length === 0 && !report.error && (
            <p className="my-4 text-sm">
              No findings are available in this report. Check scan status and coverage before
              relying on it.
            </p>
          )}
          <section aria-label="Strix findings" className="space-y-3">
            {findings
              .filter((finding) => severity === "all" || finding.severity === severity)
              .map((finding) => (
                <details key={finding.id} className="rounded-xl border bg-card p-4">
                  <summary className="cursor-pointer break-words font-medium">
                    <span className="mr-2 text-xs uppercase text-primary">{finding.severity}</span>
                    {finding.title}
                    <span className="ml-2 text-xs text-muted-foreground">
                      {finding.validation === "verified"
                        ? "Marked verified by Strix"
                        : "Reported by Strix"}
                    </span>
                  </summary>
                  {(
                    [
                      ["Description", finding.description],
                      ["Impact", finding.impact],
                      ["Target", finding.target],
                      ["Technical analysis", finding.technical_analysis],
                      ["Evidence", finding.evidence],
                      ["Reproduction", finding.poc_description],
                      ["Remediation", finding.remediation_steps],
                    ] as const
                  )
                    .filter(([, value]) => value)
                    .map(([label, value]) => (
                      <div key={label} className="mt-4">
                        <h3 className="text-sm font-semibold">{label}</h3>
                        <pre className="mt-1 whitespace-pre-wrap break-words font-mono text-xs leading-6">
                          {value}
                        </pre>
                      </div>
                    ))}
                </details>
              ))}
          </section>
          {report.run?.recommendations && (
            <section className="my-4 rounded-xl border p-4">
              <h2 className="font-semibold">Recommendations</h2>
              <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6">
                {report.run.recommendations}
              </p>
            </section>
          )}
        </>
      )}
    </PageScroll>
  );
}

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { DownloadIcon, PlayIcon, ShieldCheckIcon, SquareIcon, RefreshCwIcon } from "lucide-react";
import { Link, useSearchParams } from "@/lib/routing";
import { useProjectSessions } from "@/hooks/useConversations";
import { authenticatedFetch } from "@/lib/identity";
import { apiErrorFromResponse } from "@/lib/sessionsApi";
import { PageScroll } from "@/components/PageScroll";
import "./preproduction.css";
import { FixDashboardIssues } from "@/components/chat/FixDashboardIssues";

export interface TestCheck {
  id: string;
  category: string;
  name: string;
  platform: string;
  status: string;
  command?: string[] | null;
  cwd?: string;
  reason?: string;
  output?: string;
  duration?: number;
  reused?: boolean;
  output_truncated?: boolean;
}
export interface TestReport {
  id?: string;
  state: string;
  started_at?: number;
  finished_at?: number;
  source_changed?: boolean;
  checks: TestCheck[];
  error?: string;
  notice?: string;
  workspace?: string;
}
const CATEGORIES: Record<string, string> = {
  unit: "Unit",
  integration: "Integration",
  functional: "Functional",
  regression: "Regression",
  e2e: "End-to-end",
  security: "Security",
  static: "Lint / static analysis",
  usability: "Usability",
  accessibility: "Accessibility",
  smoke: "Smoke",
};
const escape = (value: unknown) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]!,
  );
export function reportDownload(
  report: TestReport,
  format: "json" | "html" | "csv",
  title = "Xwav Pre-Production Tests",
) {
  if (format === "json") return JSON.stringify(report, null, 2);
  if (format === "csv") {
    const cell = (value: unknown) => {
      const text = String(value ?? "");
      return '"' + (/^\s*[=+@-]/.test(text) ? "'" : "") + text.replaceAll('"', '""') + '"';
    };
    return [
      ["Category", "Platform", "Check", "Status", "Seconds", "Command", "Details"],
      ...report.checks.map((check) => [
        check.category,
        check.platform,
        check.name,
        check.status,
        check.duration,
        check.command?.join(" "),
        check.reason || check.output,
      ]),
    ]
      .map((row) => row.map(cell).join(","))
      .join("\r\n");
  }
  return `<!doctype html><html lang="en"><meta charset="utf-8"><title>${escape(title)}</title><style>body{font:16px system-ui;max-width:1000px;margin:40px auto;padding:20px}article{border:1px solid #ccd6dd;padding:16px;margin:16px 0;border-radius:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere}h1{color:#0f766e}</style><h1>${escape(title)}</h1><p>Run ${escape(report.id)} · ${escape(report.state)}</p><p>${escape(report.notice)}</p>${report.source_changed ? "<p>Workspace changed during this run. Rerun before relying on these results.</p>" : ""}${report.checks.map((check) => `<article><h2>${escape(check.name)}</h2><p>${escape(check.category)} · ${escape(check.platform)} · ${escape(check.status)} · ${escape(check.duration)}s</p><pre>${escape(check.command?.join(" "))}</pre><pre>${escape(check.reason || check.output)}</pre></article>`).join("")}</html>`;
}
async function requestReport(
  sessionId: string,
  action: string,
  signal?: AbortSignal,
): Promise<TestReport> {
  const response = await authenticatedFetch(
    `/v1/sessions/${encodeURIComponent(sessionId)}/preproduction`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
      signal,
    },
  );
  if (!response.ok) throw await apiErrorFromResponse(response);
  return response.json();
}

export function PreproductionPage() {
  const [params] = useSearchParams();
  const requestedSession = params.get("session");
  const project = params.get("project") ?? "";
  const jobs = useProjectSessions(project, !requestedSession && !!project);
  const sessionId = requestedSession ?? jobs.data?.pages[0]?.data[0]?.id ?? null;
  const client = useQueryClient();
  const queryKey = ["preproduction", sessionId];
  const query = useQuery({
    queryKey,
    enabled: !!sessionId,
    queryFn: ({ signal }) => requestReport(sessionId!, "ensure", signal),
    retry: false,
    refetchInterval: (entry) => (entry.state.data?.state === "running" ? 2000 : false),
    refetchIntervalInBackground: true,
  });
  const report = query.data;
  const [category, setCategory] = useState("all");
  const [platform, setPlatform] = useState("all");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function action(value: string) {
    if (!sessionId || busy) return;
    setBusy(true);
    setError("");
    try {
      client.setQueryData(queryKey, await requestReport(sessionId, value));
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not update the test run");
    } finally {
      setBusy(false);
    }
  }
  function download(format: "json" | "html" | "csv") {
    if (!report) return;
    const url = URL.createObjectURL(
      new Blob([reportDownload(report, format)], {
        type: format === "json" ? "application/json" : format === "html" ? "text/html" : "text/csv",
      }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `xwav-preproduction-${report.id ?? "report"}.${format}`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const checks = report?.checks ?? [];
  const count = (statuses: string[]) =>
    checks.filter((check) => statuses.includes(check.status)).length;
  const completed = count(["passed", "failed", "blocked", "error", "cancelled", "not_applicable"]);
  const filtered = checks.filter(
    (check) =>
      (category === "all" || check.category === category) &&
      (platform === "all" || check.platform === platform),
  );
  return (
    <PageScroll className="preproduction-page" maxWidthClassName="max-w-7xl">
      <main>
        <header className="preproduction-heading">
          <div>
            <p className="preproduction-eyebrow">
              <ShieldCheckIcon size={18} /> XWAV QUALITY LAB
            </p>
            <h1>Pre-Production Tests</h1>
            <p>Evidence from this job’s workspace. Real results, visible coverage gaps.</p>
          </div>
          <div className="preproduction-actions">
            <FixDashboardIssues
              key={`${sessionId}:${report?.id}`}
              sessionId={sessionId}
              kind="preproduction"
              runId={report?.id}
              disabled={!report || report.state === "running"}
            />
            {sessionId && <Link to={`/c/${encodeURIComponent(sessionId)}`}>Back to job</Link>}
            <button
              type="button"
              disabled={!sessionId || busy || report?.state === "running"}
              onClick={() => void action("start")}
            >
              <PlayIcon size={16} />
              Run again
            </button>
            {report?.state === "running" && (
              <button type="button" disabled={busy} onClick={() => void action("cancel")}>
                <SquareIcon size={15} />
                Stop tests
              </button>
            )}
          </div>
        </header>
        {!sessionId && (
          <p role="status">
            Open Pre-Production Tests from a project job. No unrelated workspace will be tested.
          </p>
        )}
        {(query.isError || error) && (
          <div role="alert" className="preproduction-warning">
            {error || (query.error instanceof Error ? query.error.message : "Runtime unavailable")}{" "}
            <button type="button" onClick={() => void query.refetch()}>
              <RefreshCwIcon size={14} />
              Retry connection
            </button>
          </div>
        )}
        {query.isPending && sessionId && (
          <p role="status">Discovering test suites and starting this job’s checks…</p>
        )}
        {report && (
          <>
            <section className="preproduction-run" aria-label="Test run status">
              <div>
                <strong role="status">
                  {report.state === "running"
                    ? "Tests running"
                    : report.state === "cancelled"
                      ? "Test run cancelled"
                      : report.state === "error"
                        ? "Run could not finish"
                        : count(["failed", "error"])
                          ? "Failures need attention"
                          : count(["blocked", "cancelled"])
                            ? "Coverage incomplete"
                            : "Configured checks passed"}
                </strong>
                <p>
                  {completed} / {checks.length} checks resolved · {report.id?.slice(0, 12)}{" "}
                  {report.started_at && `· ${new Date(report.started_at * 1000).toLocaleString()}`}
                </p>
              </div>
              <progress aria-label="Test progress" max={checks.length || 1} value={completed} />
            </section>
            {(report.error || report.source_changed) && (
              <p role="alert" className="preproduction-warning">
                {report.error ||
                  "Workspace files differ from the tested source. Run again before relying on these results."}
              </p>
            )}
            <div className="preproduction-metrics">
              {[
                ["Passed", count(["passed"])],
                ["Failed / errors", count(["failed", "error"])],
                ["Coverage gaps", count(["blocked", "cancelled"])],
                ["Not applicable", count(["not_applicable"])],
              ].map(([label, value]) => (
                <article key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </article>
              ))}
            </div>
            <p className="preproduction-notice">
              {report.notice} Passing configured checks is not a production-readiness or security
              certification. Downloads may contain project paths and test output.
            </p>
            <section className="preproduction-categories" aria-label="Test categories">
              {Object.entries(CATEGORIES).map(([key, label]) => {
                const rows = checks.filter((check) => check.category === key);
                return (
                  <button
                    type="button"
                    key={key}
                    aria-pressed={category === key}
                    onClick={() => setCategory(category === key ? "all" : key)}
                  >
                    <strong>{label}</strong>
                    <span>
                      {rows.filter((check) => check.status === "passed").length} passed ·{" "}
                      {rows.length} checks
                    </span>
                  </button>
                );
              })}
            </section>
            <div className="preproduction-toolbar">
              <label>
                Platform
                <select
                  aria-label="Filter test platform"
                  value={platform}
                  onChange={(event) => setPlatform(event.target.value)}
                >
                  <option value="all">All platforms</option>
                  <option value="shared">Shared code</option>
                  <option value="web">Web</option>
                  <option value="android">Android</option>
                  <option value="ios">iOS</option>
                </select>
              </label>
              <button
                type="button"
                onClick={() => {
                  setPlatform("all");
                  setCategory("all");
                }}
              >
                Show all checks
              </button>
              <div className="preproduction-downloads">
                {(["json", "html", "csv"] as const).map((format) => (
                  <button type="button" key={format} onClick={() => download(format)}>
                    <DownloadIcon size={14} />
                    Download {format.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
            <section className="preproduction-results" aria-label="Test results">
              {filtered.map((check) => (
                <article key={check.id} className={`preproduction-check state-${check.status}`}>
                  <header>
                    <div>
                      <span className="preproduction-badge">
                        {check.status.replaceAll("_", " ")}
                      </span>
                      <h2>{check.name}</h2>
                    </div>
                    <span>
                      {check.platform} · {CATEGORIES[check.category]}{" "}
                      {check.duration != null && `· ${check.duration}s`}
                    </span>
                  </header>
                  {check.reason && <p>{check.reason}</p>}
                  {check.reused && <p>Result reused from an identical command in this run.</p>}
                  {check.command && <code>{check.command.join(" ")}</code>}
                  {check.output_truncated && <p>Output shows the last 16000 bytes.</p>}
                  {check.output && (
                    <details>
                      <summary>View output</summary>
                      <pre>{check.output}</pre>
                    </details>
                  )}
                </article>
              ))}
              {!filtered.length && <p>No checks match these filters.</p>}
            </section>
          </>
        )}
        <details className="preproduction-setup">
          <summary>Configure comprehensive project and native-device suites</summary>
          <p>
            Existing package scripts and Python/Flutter/Android suites are discovered automatically.
            For explicit coverage, add <code>.xwav/preproduction.json</code> in the job’s workspace.
            Commands run there without an interactive terminal, once per identical command. No
            packages, simulators or devices are installed automatically. Each command has a timeout;
            closing this page keeps the run active. Opening it again restores the latest report.
          </p>
          <pre>
            {JSON.stringify(
              {
                checks: [
                  {
                    name: "Web E2E flows",
                    category: "e2e",
                    platform: "web",
                    command: ["npm", "run", "test:e2e"],
                    timeout: 300,
                  },
                  {
                    name: "Android instrumentation",
                    category: "integration",
                    platform: "android",
                    cwd: "android",
                    command: ["sh", "gradlew", "connectedDebugAndroidTest"],
                    timeout: 600,
                  },
                ],
              },
              null,
              2,
            )}
          </pre>
          <p>
            Supported categories: {Object.keys(CATEGORIES).join(", ")}. Platforms: shared, web,
            android, ios. iOS native tests need a macOS host and an available Xcode
            simulator/device. Missing checks stay visible as gaps.
          </p>
        </details>
      </main>
    </PageScroll>
  );
}

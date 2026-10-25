import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { GaugeIcon, DownloadIcon, PlayIcon, SquareIcon } from "lucide-react";
import { Link, useSearchParams } from "@/lib/routing";
import { useProjectSessions } from "@/hooks/useConversations";
import { authenticatedFetch } from "@/lib/identity";
import { apiErrorFromResponse } from "@/lib/sessionsApi";
import { PageScroll } from "@/components/PageScroll";
import { reportDownload, type TestReport, type TestCheck } from "./PreproductionPage";
import "./preproduction.css";
import "./loadtesting.css";

interface Metrics {
  requests: number;
  errors: number;
  error_percent: number;
  rps: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  max_ms: number;
  duration: number;
  peak_concurrency: number;
  bytes_sampled: number;
  sample_errors: string[];
  platforms: Record<string, { requests: number; errors: number; p95_ms: number }>;
  series: {
    second: number;
    requests: number;
    p95_ms: number;
    errors: number;
    concurrency: number;
  }[];
}
type LoadCheck = TestCheck & {
  metrics?: Metrics;
  target_requests?: number | null;
  assessment?: string;
  config?: {
    durations: Record<string, number>;
    request_mode?: "count" | "duration";
    max_requests: number;
    requests_per_second: number;
    max_p95_ms: number;
    max_error_percent: number;
  };
};
type Report = Omit<TestReport, "checks"> & { target?: string; checks: LoadCheck[] };

async function requestReport(
  session: string,
  action: string,
  signal?: AbortSignal,
  maxRequests?: number,
): Promise<Report> {
  const response = await authenticatedFetch(
    `/v1/sessions/${encodeURIComponent(session)}/loadtesting`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action,
        ...(maxRequests !== undefined ? { max_requests: maxRequests } : {}),
      }),
      signal,
    },
  );
  if (!response.ok) throw await apiErrorFromResponse(response);
  return response.json();
}

function sparkline(series: Metrics["series"]) {
  const maximum = Math.max(1, ...series.map((point) => point.p95_ms));
  const stride = Math.max(1, Math.ceil(series.length / 120));
  return series
    .filter((_, index) => index % stride === 0)
    .map(
      (point, index, all) =>
        `${(index * 400) / Math.max(1, all.length - 1)},${75 - (point.p95_ms * 70) / maximum}`,
    )
    .join(" ");
}

export function LoadTestingPage() {
  const [params] = useSearchParams();
  const requested = params.get("session"),
    project = params.get("project") ?? "";
  const jobs = useProjectSessions(project, !requested && !!project);
  const session = requested ?? (project ? (jobs.data?.pages[0]?.data[0]?.id ?? null) : null);
  const client = useQueryClient(),
    key = ["loadtesting", session];
  const query = useQuery({
    queryKey: key,
    enabled: !!session,
    retry: false,
    queryFn: ({ signal }) => requestReport(session!, "ensure", signal),
    refetchInterval: (entry) => (entry.state.data?.state === "running" ? 2000 : false),
    refetchIntervalInBackground: true,
  });
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [requestLimit, setRequestLimit] = useState<string | null>(null);
  const report = query.data,
    checks = report?.checks ?? [],
    running = report?.state === "running";
  const requestText = requestLimit ?? String(checks[0]?.config?.max_requests ?? 2000);
  const requestCount = Number(requestText);
  const validRequestCount =
    /^\d+$/.test(requestText) &&
    Number.isInteger(requestCount) &&
    requestCount >= 1 &&
    requestCount <= 100_000_000;
  async function action(value: string) {
    if (!session || busy || (value === "start" && !validRequestCount)) return;
    setBusy(true);
    setError("");
    try {
      client.setQueryData(
        key,
        await requestReport(
          session,
          value,
          undefined,
          value === "start" ? requestCount : undefined,
        ),
      );
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not update load test");
    } finally {
      setBusy(false);
    }
  }
  function download(format: "json" | "html" | "csv") {
    if (!report) return;
    const exported = {
      ...report,
      checks: checks.map((check) => ({
        ...check,
        output: JSON.stringify(
          {
            metrics: check.metrics,
            assessment: check.assessment,
            config: check.config,
            target_requests: check.target_requests,
          },
          null,
          2,
        ),
      })),
    };
    const objectUrl = URL.createObjectURL(
      new Blob([reportDownload(exported, format, "Xwav Load Testing")], {
        type: format === "json" ? "application/json" : format === "html" ? "text/html" : "text/csv",
      }),
    );
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = `xwav-loadtesting-${report.id ?? "report"}.${format}`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  }
  const samples = checks.reduce((total, check) => total + (check.metrics?.requests ?? 0), 0);
  const errors = checks.reduce((total, check) => total + (check.metrics?.errors ?? 0), 0);
  const config = checks[0]?.config;
  return (
    <PageScroll className="preproduction-page loadtesting-page" maxWidthClassName="max-w-6xl">
      <header className="preproduction-heading">
        <div>
          <p className="preproduction-eyebrow">
            <GaugeIcon size={16} /> XWAV PERFORMANCE LAB
          </p>
          <h1>Load Testing</h1>
          <p>Find slowdowns before your users do. Controlled traffic, measurable results.</p>
        </div>
        <div className="preproduction-actions">
          {session && <Link to={`/c/${encodeURIComponent(session)}`}>Back to job</Link>}
          {running ? (
            <button type="button" disabled={busy} onClick={() => action("cancel")}>
              <SquareIcon size={15} /> Stop run
            </button>
          ) : (
            <button
              type="button"
              disabled={!session || busy || !validRequestCount}
              onClick={() => action("start")}
            >
              <PlayIcon size={15} /> Run again
            </button>
          )}
        </div>
      </header>
      <div className="loadtesting-request-control">
        <label htmlFor="loadtesting-request-count">Total requests</label>
        <input
          id="loadtesting-request-count"
          type="number"
          min="1"
          max="100000000"
          step="1"
          inputMode="numeric"
          value={requestText}
          disabled={running || busy}
          aria-invalid={!validRequestCount}
          aria-describedby="loadtesting-request-help"
          onChange={(event) => setRequestLimit(event.target.value)}
        />
        <p id="loadtesting-request-help">
          Enter 1–100,000,000 total requests, then choose Run again. The total is split across all
          four profiles. The run continues until that count is reached or you stop it; rate and
          concurrency limits remain active. Large totals can take hours or days.
        </p>
        {!validRequestCount && <p role="alert">Enter a whole number from 1 to 100,000,000.</p>}
      </div>
      {!session && <p role="status">Open Load Testing from a job with an app workspace.</p>}
      {query.isPending && session && <p role="status">Connecting to this job’s app…</p>}
      {(error || query.error || report?.error) && (
        <p role="alert">{error || query.error?.message || report?.error}</p>
      )}
      {report && (
        <>
          <section className="preproduction-run" aria-label="Load test status">
            <h2>
              {running
                ? "Testing in progress"
                : report.state === "cancelled"
                  ? "Run stopped"
                  : report.state === "error"
                    ? "Run unavailable"
                    : checks.some((c) => c.status === "failed")
                      ? "Performance thresholds exceeded"
                      : checks.some((c) => c.status === "blocked")
                        ? "Coverage incomplete"
                        : "Configured profiles passed"}
            </h2>
            <p>
              {report.id?.slice(0, 12)} · {report.target ?? "Discovering local app"}
            </p>
            <progress
              aria-label="Load test progress"
              max={4}
              value={checks.filter((c) => !["pending", "running"].includes(c.status)).length}
            />
          </section>
          {config?.request_mode === "count" && (
            <progress aria-label="Request progress" max={config.max_requests} value={samples} />
          )}
          <div className="loadtesting-summary" aria-label="Load test summary">
            <div>
              <span>Requests sampled</span>
              <strong>{samples.toLocaleString()}</strong>
              {config?.request_mode === "count" && (
                <small>of {config.max_requests.toLocaleString()} requested</small>
              )}
            </div>
            <div>
              <span>Request errors</span>
              <strong>{errors}</strong>
            </div>
            <div>
              <span>Profiles passed</span>
              <strong>{checks.filter((c) => c.status === "passed").length} / 4</strong>
            </div>
            <div>
              <span>Traffic limit</span>
              <strong>{config?.requests_per_second ?? "—"} req/s</strong>
            </div>
          </div>
          <p className="preproduction-notice">{report.notice}</p>
          {config?.request_mode !== "count" && (
            <p className="preproduction-notice">
              This report used fixed durations. Run again to send the chosen total instead.
            </p>
          )}
          {report.source_changed && (
            <p role="status">
              App source changed during this run. Run again to measure the latest version.
            </p>
          )}
          {config && (
            <p className="preproduction-notice">
              {config.request_mode === "count" ? "Requested total" : "Timed-run budget"}:{" "}
              {config.max_requests.toLocaleString()} requests. Thresholds: p95 ≤ {config.max_p95_ms}{" "}
              ms; errors ≤ {config.max_error_percent}%. Latency includes connection, headers and up
              to 16 KiB of body; payload sampling is capped. Counts are exact; latency percentiles
              use up to 4,096 samples for larger runs. Requests are read-only GETs; redirects are
              not followed.
            </p>
          )}
          <div className="preproduction-downloads">
            {(["json", "html", "csv"] as const).map((format) => (
              <button type="button" key={format} onClick={() => download(format)}>
                <DownloadIcon size={15} /> Download {format.toUpperCase()}
              </button>
            ))}
          </div>
          <section className="loadtesting-profiles" aria-label="Performance profiles">
            {checks.map((check) => (
              <article key={check.id}>
                <header>
                  <h2>{check.name}</h2>
                  <span className={`load-status load-status-${check.status}`}>{check.status}</span>
                </header>
                <p>
                  {
                    (
                      {
                        load: "Steady concurrent traffic",
                        stress: "Gradually increasing concurrent traffic",
                        spike: "Sudden traffic surge and recovery",
                        soak: "Sustained traffic over time",
                      } as Record<string, string>
                    )[check.id]
                  }{" "}
                  ·{" "}
                  {check.target_requests != null
                    ? `${check.target_requests.toLocaleString()} requests allocated`
                    : `${check.config?.durations[check.id]}s configured`}
                </p>
                {check.reason && <p role="status">{check.reason}</p>}
                {check.metrics && (
                  <>
                    <dl className="loadtesting-metrics">
                      {Object.entries({
                        Requests: check.metrics.requests,
                        Errors: `${check.metrics.error_percent}%`,
                        Throughput: `${check.metrics.rps} req/s`,
                        p50: `${check.metrics.p50_ms} ms`,
                        p95: `${check.metrics.p95_ms} ms`,
                        p99: `${check.metrics.p99_ms} ms`,
                        "Peak concurrency": check.metrics.peak_concurrency,
                        "Measured time": `${check.metrics.duration}s`,
                      }).map(([label, value]) => (
                        <div key={label}>
                          <dt>{label}</dt>
                          <dd>{value}</dd>
                        </div>
                      ))}
                    </dl>
                    <svg
                      role="img"
                      aria-label={`${check.name} p95 latency over time`}
                      viewBox="0 0 400 80"
                      className="loadtesting-sparkline"
                    >
                      <title>Latency trend; full time series available in downloads</title>
                      <polyline
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        points={sparkline(check.metrics.series)}
                      />
                    </svg>
                    <details>
                      <summary>Platform samples and evidence</summary>
                      <table>
                        <caption>HTTP user-agent samples; shared backend</caption>
                        <thead>
                          <tr>
                            <th>Platform</th>
                            <th>Requests</th>
                            <th>Errors</th>
                            <th>p95 ms</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(check.metrics.platforms).map(([name, row]) => (
                            <tr key={name}>
                              <td>{name}</td>
                              <td>{row.requests}</td>
                              <td>{row.errors}</td>
                              <td>{row.p95_ms}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <pre>{JSON.stringify(check.metrics, null, 2)}</pre>
                    </details>
                  </>
                )}
                {check.assessment && <p>{check.assessment}</p>}
              </article>
            ))}
          </section>
          <details className="preproduction-setup">
            <summary>Configure traffic, endpoints and longer endurance runs</summary>
            <p>
              Save .xwav/loadtesting.json in the job workspace. No load-testing packages or external
              services are required.
            </p>
            <pre>
              {JSON.stringify(
                {
                  paths: ["/"],
                  concurrency: 4,
                  max_concurrency: 16,
                  requests_per_second: 20,
                  max_requests: 10000,
                  max_p95_ms: 1000,
                  max_error_percent: 1,
                  durations: { load: 8, stress: 12, spike: 10, soak: 300 },
                },
                null,
                2,
              )}
            </pre>
            <p>
              Hard limits: 16 concurrent requests, 50 requests/second, 100,000,000 requests total,
              with rate and concurrency limits active throughout. Fixed durations apply only to
              automatic timed runs (up to 120 seconds per short profile and 30 minutes of soak). Run
              again completes the entered request total instead. These tests measure HTTP response
              performance; native-only apps require their own backend or native tooling.
            </p>
          </details>
        </>
      )}
    </PageScroll>
  );
}

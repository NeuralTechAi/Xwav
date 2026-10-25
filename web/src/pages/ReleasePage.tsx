import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  RocketIcon,
  PackageCheckIcon,
  DownloadIcon,
  SquareIcon,
  GlobeIcon,
  SmartphoneIcon,
  MonitorIcon,
  ArrowLeftIcon,
  ExternalLinkIcon,
} from "lucide-react";
import { Link, useSearchParams } from "@/lib/routing";
import { useProjectSessions } from "@/hooks/useConversations";
import { authenticatedFetch } from "@/lib/identity";
import { apiErrorFromResponse } from "@/lib/sessionsApi";
import { triggerBrowserDownload } from "@/hooks/useFileContent";
import { PageScroll } from "@/components/PageScroll";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import "./preproduction.css";
import "./release.css";

type Target = "web" | "android" | "ios" | "windows";
interface Plan {
  target: Target;
  ready: boolean;
  reason: string;
  setup?: string;
  android_licenses_required?: boolean;
}
interface Artifact {
  name: string;
  bytes: number;
  sha256: string;
  installable: boolean;
}
interface Report {
  id?: string;
  state: string;
  error?: string;
  notice?: string;
  source_changed?: boolean;
  cloud?: { repository: string; message?: string };
  cloud_run_url?: string;
  source_commit?: string;
  plans?: Plan[];
  artifacts?: Artifact[];
  urls?: string[];
  checks: {
    target: Target;
    operation: string;
    name: string;
    status: string;
    phase?: string;
    output?: string;
    live_output?: string;
    reason?: string;
    duration?: number;
  }[];
}
const TARGETS = { web: "Web", android: "Android", ios: "iOS", windows: "Windows" };
const PROVIDERS = {
  vercel: {
    name: "Vercel",
    hint: "Uses Vercel login or VERCEL_TOKEN in this job. Link an existing project to update it.",
  },
  netlify: {
    name: "Netlify",
    hint: "Uses Netlify login or NETLIFY_AUTH_TOKEN. Choose a site ID or link a site in this project.",
  },
  cloudflare: {
    name: "Cloudflare Pages",
    hint: "Uses Wrangler login or CLOUDFLARE_API_TOKEN. Enter your existing Pages project name.",
  },
  railway: {
    name: "Railway",
    hint: "Uses Railway login or RAILWAY_TOKEN and a linked project. Supports server apps; configure its public domain in Railway.",
  },
  project: {
    name: "Project deployment workflow",
    hint: "Uses the project's configured deployment script and its existing account connections.",
  },
};
type Provider = keyof typeof PROVIDERS;

async function requestRelease(
  session: string,
  action: string,
  target: Target,
  operation: string,
  provider: Provider,
  site: string,
  signal?: AbortSignal,
  acceptAndroidLicenses = false,
  engine = "local",
  channel = "testing",
  repository = "",
): Promise<Report> {
  const response = await authenticatedFetch(
    `/v1/sessions/${encodeURIComponent(session)}/releases`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action,
        engine,
        channel,
        repository,
        target,
        operation,
        provider,
        site,
        accept_android_licenses: acceptAndroidLicenses,
      }),
      signal,
    },
  );
  if (!response.ok) throw await apiErrorFromResponse(response);
  return response.json();
}

export function ReleasePage({ mode }: { mode: "deploy" | "download" }) {
  const [params] = useSearchParams();
  const requested = params.get("session"),
    project = params.get("project") ?? "";
  const jobs = useProjectSessions(project, !requested && !!project);
  const session = requested ?? (project ? (jobs.data?.pages[0]?.data[0]?.id ?? null) : null);
  const [target, setTarget] = useState<Target>(mode === "deploy" ? "web" : "windows");
  const [provider, setProvider] = useState<Provider | "">("");
  const [engine, setEngine] = useState("local");
  const [channel, setChannel] = useState("testing");
  const [repository, setRepository] = useState("");
  const [setupMessage, setSetupMessage] = useState("");
  const [productionConfirmed, setProductionConfirmed] = useState(false);
  const [site, setSite] = useState("");
  const [siteInput, setSiteInput] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setSite(siteInput), 300);
    return () => clearTimeout(timer);
  }, [siteInput]);
  const [acceptAndroidLicenses, setAcceptAndroidLicenses] = useState(false);
  const [setupOpen, setSetupOpen] = useState(false);
  const [focusCloud, setFocusCloud] = useState(false);
  const cloudSetup = useRef<HTMLElement>(null);
  useEffect(() => {
    if (focusCloud && engine === "github" && cloudSetup.current) {
      cloudSetup.current.scrollIntoView?.({ block: "start", behavior: "smooth" });
      cloudSetup.current.querySelector("input")?.focus();
      setFocusCloud(false);
    }
  }, [focusCloud, engine]);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [downloading, setDownloading] = useState<string | null>(null);
  const operation = mode === "deploy" ? "deploy" : "build";
  const client = useQueryClient();
  const key = ["releases", session, target, operation, provider, site, engine, channel];
  const query = useQuery({
    queryKey: key,
    enabled: !!session,
    retry: false,
    queryFn: ({ signal }) =>
      requestRelease(
        session!,
        "status",
        target,
        operation,
        provider || "vercel",
        site,
        signal,
        false,
        engine,
        channel,
      ),
    refetchInterval: (entry) => (entry.state.data?.state === "running" ? 2000 : false),
    refetchIntervalInBackground: true,
  });
  const report = query.data,
    check = report?.checks[0];
  const running = report?.state === "running";
  const plan = report?.plans?.find((item) => item.target === target);
  const completed =
    !busy && report?.state === "complete" && check?.status === "passed" && check.target === target;
  const mobileTarget = target === "android" || target === "ios";
  const needsLicence =
    target === "android" && !!plan?.android_licenses_required && !acceptAndroidLicenses;
  const needsProductionConfirmation =
    engine === "github" && channel === "production" && mode === "deploy" && !productionConfirmed;
  const canStart =
    !!plan?.ready &&
    !needsLicence &&
    !needsProductionConfirmation &&
    !query.isFetching &&
    !query.isError &&
    (target !== "web" || (site === siteInput && (mode !== "deploy" || !!provider)));
  const setupReason = query.isFetching
    ? "Checking this project's build requirements…"
    : query.error instanceof Error
      ? query.error.message
      : plan?.reason ||
        (!plan?.ready && report?.error) ||
        (needsLicence
          ? "Accept the Android SDK licence before downloading and setting up its build tools."
          : needsProductionConfirmation
            ? "Confirm production publishing before starting this release."
            : !plan?.ready
              ? "Could not determine build readiness. Check the job connection and try again."
              : "The project is ready to build.");
  const Icon = mode === "deploy" ? RocketIcon : PackageCheckIcon;
  function startOrSetup() {
    if (!canStart) {
      setSetupOpen(true);
      return;
    }
    setSetupOpen(false);
    void action("start");
  }
  async function action(value: "start" | "cancel" | "prepare" | "verify") {
    if (!session || busy || (value === "start" && !canStart)) return;
    setBusy(true);
    setError("");
    try {
      const result = await requestRelease(
        session,
        value,
        target,
        operation,
        provider || "vercel",
        site,
        undefined,
        acceptAndroidLicenses,
        engine,
        channel,
        repository,
      );
      if (result.cloud?.message) setSetupMessage(result.cloud.message);
      if (result.error) setError(result.error);
      client.setQueryData(key, result);
      await client.invalidateQueries({ queryKey: ["releases", session], refetchType: "none" });
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Release request failed");
    } finally {
      setBusy(false);
    }
  }
  async function download(artifact: Artifact) {
    if (!session || !report?.id || downloading || !completed || running || report.source_changed)
      return;
    setDownloading(artifact.name);
    setError("");
    try {
      const response = await authenticatedFetch(
        `/v1/sessions/${encodeURIComponent(session)}/releases/${report.id}/${encodeURIComponent(artifact.name)}`,
      );
      if (!response.ok) throw await apiErrorFromResponse(response);
      if (response.headers.get("content-type")?.includes("application/json"))
        throw new Error("The runtime did not return an installer.");
      const blob = await response.blob();
      if (blob.size !== artifact.bytes)
        throw new Error("Package download was incomplete. Try again.");
      triggerBrowserDownload(blob, artifact.name);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Download failed");
    } finally {
      setDownloading(null);
    }
  }
  function downloadReport() {
    if (report)
      triggerBrowserDownload(
        new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }),
        `xwav-release-${report.id ?? "readiness"}.json`,
      );
  }
  return (
    <PageScroll className="preproduction-page release-page" data-testid="release-page">
      <header className="preproduction-heading">
        <div>
          <p className="preproduction-eyebrow">
            <Icon size={16} /> XWAV RELEASE STUDIO
          </p>
          <h1>{mode === "deploy" ? "Deploy your app" : "Installable downloads"}</h1>
          <p>
            {mode === "deploy"
              ? "Choose a destination. Xwav builds, packages, then publishes from your job."
              : "Build a real app package for your chosen platform, then download it."}
          </p>
        </div>
        <Link className="release-back" to={session ? `/c/${session}` : "/"}>
          <ArrowLeftIcon size={15} /> Back to job
        </Link>
      </header>
      <Dialog open={setupOpen} onOpenChange={setSetupOpen}>
        <DialogContent className="release-setup-dialog sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>
              Set up {TARGETS[target]} {mode === "deploy" ? "deployment" : "build"}
            </DialogTitle>
            <DialogDescription>
              Complete the requirements below, then continue this job’s{" "}
              {mode === "deploy" ? "release" : "build"}.
            </DialogDescription>
          </DialogHeader>
          <p role="status" className="release-readiness">
            {setupReason}
          </p>
          {target === "android" && plan?.android_licenses_required && (
            <label className="release-setup-consent">
              <input
                type="checkbox"
                checked={acceptAndroidLicenses}
                onChange={(event) => setAcceptAndroidLicenses(event.target.checked)}
              />
              <span>
                I accept the{" "}
                <a
                  href="https://developer.android.com/studio/terms"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Android SDK licence
                </a>{" "}
                for this build.
              </span>
            </label>
          )}
          {engine === "github" && channel === "production" && mode === "deploy" && (
            <label className="release-setup-consent">
              <input
                type="checkbox"
                checked={productionConfirmed}
                onChange={(event) => setProductionConfirmed(event.target.checked)}
              />
              <span>I confirm production publishing for this job.</span>
            </label>
          )}
          {!plan?.ready && !query.isFetching && (
            <div className="release-setup-guidance">
              <p>
                {target === "ios"
                  ? "iOS needs a Mac with Xcode and matching Apple signing credentials. GitHub Actions provides a Mac build worker."
                  : mode === "deploy"
                    ? "Google Play needs an app ID, version/build number, signing key and publishing credentials. A development APK can be built from Installable downloads without a Play account."
                    : "Android build tools are installed automatically on supported job computers after licence acceptance. A compatible app frontend or a native build command is required."}
              </p>
              <p>
                {engine === "local"
                  ? "Use GitHub Actions for a guided cloud workflow, or configure this job’s native build/publish commands in .xwav/release.json and check readiness again."
                  : "Complete the repository, workflow and environment setup in the Cloud setup panel, then check its connection and signing setup."}
              </p>
            </div>
          )}
          <DialogFooter className="release-setup-actions">
            <Button variant="outline" onClick={() => setSetupOpen(false)}>
              Close setup
            </Button>
            {(!plan?.ready || query.isError) && (
              <Button
                variant="outline"
                disabled={query.isFetching}
                onClick={() => void query.refetch()}
              >
                Check again
              </Button>
            )}
            {!plan?.ready && (
              <Button
                variant="outline"
                onClick={() => {
                  setEngine("github");
                  setSetupOpen(false);
                  setFocusCloud(true);
                  setError("");
                }}
              >
                {engine === "local" ? "Use GitHub Actions" : "Open cloud setup"}
              </Button>
            )}
            <Button disabled={!canStart || busy || running} onClick={startOrSetup}>
              Continue {mode === "deploy" ? "deployment" : "build"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {!session ? (
        <p role="status" className="preproduction-setup">
          Open this page from a saved job, or create a job in this project first. Nothing is
          published by opening this page.
        </p>
      ) : (
        <>
          <div className="release-layout">
            <section className="release-card" aria-label="Release destination">
              <h2>{mode === "deploy" ? "Deployment platform" : "App platform"}</h2>
              <label className="release-field">
                Build computer
                <select
                  aria-label="Build computer"
                  value={engine}
                  disabled={busy || running}
                  onChange={(event) => {
                    setEngine(event.target.value);
                    setSetupMessage("");
                    setError("");
                  }}
                >
                  <option value="local">This job (on-demand tools)</option>
                  <option value="github">GitHub Actions (Linux / macOS / Windows)</option>
                </select>
              </label>
              {engine === "github" && (
                <section ref={cloudSetup} aria-label="Cloud setup" className="release-cloud-setup">
                  <h3>Connect once, build on demand</h3>
                  <p className="preproduction-notice">
                    Connect GitHub inside this job with gh auth login or a scoped GH_TOKEN. Xwav
                    uses this job’s connection; credentials are never written into project files.
                  </p>
                  <label className="release-field">
                    GitHub repository
                    <input
                      aria-label="GitHub repository"
                      placeholder="owner/repository"
                      maxLength={200}
                      value={repository}
                      disabled={running || busy}
                      onChange={(event) => setRepository(event.target.value)}
                    />
                  </label>
                  <div className="preproduction-actions">
                    <button
                      type="button"
                      disabled={
                        busy || running || !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository)
                      }
                      onClick={() => void action("prepare")}
                    >
                      Prepare cloud workflow
                    </button>
                    <button
                      type="button"
                      disabled={busy || running}
                      onClick={() => void action("verify")}
                    >
                      Check connection & signing setup
                    </button>
                  </div>
                  {setupMessage && <p role="status">{setupMessage}</p>}
                  <ol className="preproduction-notice">
                    <li>
                      Prepare the workflow, then review, commit and push it to the repository’s
                      default branch.
                    </li>
                    <li>
                      Create xwav-build, xwav-testing and xwav-production environments in GitHub.
                      Put signing keys and provider tokens in their environment secrets.
                    </li>
                    <li>
                      Add required reviewers to xwav-production. Choose a platform and check its
                      connection before starting.
                    </li>
                  </ol>
                  {(report?.cloud?.repository ||
                    /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository)) && (
                    <a
                      target="_blank"
                      rel="noopener noreferrer"
                      href={`https://github.com/${report?.cloud?.repository || repository}/settings/environments`}
                    >
                      Open GitHub environments & secrets <ExternalLinkIcon size={14} />
                    </a>
                  )}
                  <details>
                    <summary>Required credentials and platform setup</summary>
                    <p className="preproduction-notice">
                      Android downloads use a development APK. Play uploads need
                      XWAV_ANDROID_KEYSTORE_B64, XWAV_ANDROID_KEYSTORE_PASSWORD,
                      XWAV_ANDROID_KEY_ALIAS, XWAV_ANDROID_KEY_PASSWORD and XWAV_GOOGLE_PLAY_JSON.
                      Create the app in Play Console first.
                    </p>
                    <p className="preproduction-notice">
                      iOS needs XWAV_IOS_CERTIFICATE_B64, XWAV_IOS_CERTIFICATE_PASSWORD,
                      XWAV_IOS_PROFILE_B64 and XWAV_IOS_EXPORT_OPTIONS_B64. Store uploads also need
                      XWAV_APPLE_API_JSON (fastlane API key JSON). Create the app in App Store
                      Connect first. Certificates and profiles must match app_id.
                    </p>
                    <p className="preproduction-notice">
                      Web uses the selected provider’s token and project identifiers. Set app_id,
                      app_version and a unique build_number in .xwav/release.json before store
                      submission. Use GitHub variables for VERCEL_ORG_ID, VERCEL_PROJECT_ID,
                      NETLIFY_SITE_ID and CLOUDFLARE_ACCOUNT_ID as applicable.
                    </p>
                  </details>
                </section>
              )}
              {engine === "github" && mode === "deploy" && (
                <>
                  <label className="release-field">
                    Publishing destination
                    <select
                      aria-label="Publishing destination"
                      value={channel}
                      disabled={busy || running}
                      onChange={(event) => {
                        setChannel(event.target.value);
                        setProductionConfirmed(false);
                      }}
                    >
                      <option value="testing">
                        Testing — preview / Play internal / TestFlight
                      </option>
                      <option value="production">
                        Production — live web / Play / App Store upload
                      </option>
                    </select>
                  </label>
                  {channel === "production" && (
                    <label className="preproduction-notice">
                      <input
                        type="checkbox"
                        checked={productionConfirmed}
                        disabled={busy || running}
                        onChange={(event) => setProductionConfirmed(event.target.checked)}
                      />{" "}
                      Publish this committed revision to production. App Store uploads still require
                      review and release in App Store Connect.
                    </label>
                  )}
                </>
              )}
              <div
                className="release-platforms"
                role="group"
                aria-label="App platform"
                data-platforms={mode === "deploy" ? 3 : 4}
              >
                {(mode === "deploy"
                  ? (["web", "android", "ios"] as const)
                  : (["windows", "android", "ios", "web"] as const)
                ).map((value) => {
                  const PlatformIcon =
                    value === "web"
                      ? GlobeIcon
                      : value === "windows"
                        ? MonitorIcon
                        : SmartphoneIcon;
                  return (
                    <button
                      type="button"
                      key={value}
                      aria-pressed={target === value}
                      disabled={busy || running}
                      onClick={() => {
                        setTarget(value);
                        setError("");
                      }}
                    >
                      <PlatformIcon size={20} />
                      {TARGETS[value]}
                    </button>
                  );
                })}
              </div>
              {mode === "deploy" && target === "web" && (
                <>
                  <label className="release-field">
                    Web destination
                    <select
                      aria-label="Web deployment destination"
                      value={provider}
                      disabled={busy || running}
                      onChange={(event) => {
                        setProvider(event.target.value as Provider);
                        setSite("");
                        setSiteInput("");
                      }}
                    >
                      <option value="" disabled>
                        Choose a destination
                      </option>
                      {Object.entries(PROVIDERS).map(([id, item]) => (
                        <option key={id} value={id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <p className="preproduction-notice">
                    {provider ? PROVIDERS[provider].hint : "Choose where to publish this app."}
                  </p>
                  {["cloudflare", "netlify", "railway"].includes(provider) && (
                    <label className="release-field">
                      {provider === "cloudflare"
                        ? "Pages project name"
                        : provider === "netlify"
                          ? "Site ID (optional if linked)"
                          : "Service name (optional if linked)"}
                      <input
                        aria-label="Destination project"
                        maxLength={200}
                        value={siteInput}
                        disabled={busy || running}
                        onChange={(event) => setSiteInput(event.target.value)}
                        placeholder={
                          provider === "cloudflare" ? "my-app" : "Use linked destination"
                        }
                      />
                    </label>
                  )}
                </>
              )}
              <p className="preproduction-notice">
                {target === "android"
                  ? mode === "download"
                    ? "Automatic Android builds produce an installable development APK. Store releases require your signing and publishing workflow."
                    : "Build an Android package and submit through your configured Google Play workflow."
                  : target === "ios"
                    ? "Signed IPA builds require Apple provisioning, a Mac with Xcode or a cloud build workflow. iPhone installation depends on the chosen distribution profile."
                    : target === "windows"
                      ? "Compatible web frontends are packaged as a Windows installer. Windows or Wine is needed for local packaging; a cloud build can also be configured."
                      : mode === "download"
                        ? "Download the built website as a ZIP. Backend services need their own hosting."
                        : "Account access is configured in the job runtime. Xwav does not copy host credentials into jobs."}
              </p>
              {target === "android" && plan?.android_licenses_required && (
                <label className="preproduction-notice">
                  <input
                    type="checkbox"
                    checked={acceptAndroidLicenses}
                    disabled={running || busy}
                    onChange={(event) => setAcceptAndroidLicenses(event.target.checked)}
                  />{" "}
                  I accept the{" "}
                  <a
                    href="https://developer.android.com/studio/terms"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Android SDK licence
                  </a>{" "}
                  for automatic setup in this job.
                </label>
              )}
              {plan?.ready && plan.setup && <p className="preproduction-notice">{plan.setup}</p>}
              <div className="release-readiness" role="status">
                {query.isFetching
                  ? "Checking project and build tools…"
                  : mode === "deploy" && target === "web" && !provider
                    ? "Choose a web deployment destination."
                    : canStart
                      ? "Ready to start. Provider or store authentication is checked by its publishing workflow."
                      : setupReason}
              </div>
              <div className="preproduction-actions">
                <button
                  type="button"
                  className="release-primary"
                  disabled={busy || running || (!mobileTarget && !canStart)}
                  aria-describedby={
                    mobileTarget && !canStart ? "release-mobile-setup-hint" : undefined
                  }
                  onClick={startOrSetup}
                >
                  <Icon size={16} />
                  {running
                    ? "Working…"
                    : mode === "deploy"
                      ? "Build & deploy"
                      : target === "web"
                        ? "Build web package"
                        : "Build installer"}
                </button>
                {running && (
                  <button type="button" disabled={busy} onClick={() => void action("cancel")}>
                    <SquareIcon size={15} /> Stop
                  </button>
                )}
              </div>
              {mobileTarget && !canStart && !running && (
                <p id="release-mobile-setup-hint" className="preproduction-notice">
                  Setup is required. Click{" "}
                  {mode === "deploy" ? "Build & deploy" : "Build installer"} to see the next steps.
                </p>
              )}
              {mode === "deploy" && (
                <p className="preproduction-notice">
                  Build & deploy publishes to the selected destination and may use your provider's
                  paid resources.
                </p>
              )}
            </section>
            <section className="release-card" aria-label="Release progress">
              <h2>
                {running
                  ? (check?.phase ?? "Starting build")
                  : completed
                    ? (check?.phase ?? "Release ready")
                    : report?.state === "error"
                      ? "Needs attention"
                      : "Build activity"}
              </h2>
              {report?.cloud_run_url && (
                <a href={report.cloud_run_url} target="_blank" rel="noopener noreferrer">
                  Open cloud build logs & approval <ExternalLinkIcon size={14} />
                </a>
              )}
              {report?.source_commit && (
                <p className="preproduction-notice">
                  Source revision: {report.source_commit.slice(0, 12)}
                </p>
              )}
              {!check && (
                <p className="preproduction-notice">
                  No release started. Build tools run only when you choose an action.
                </p>
              )}
              {check && (
                <p>
                  {TARGETS[check.target]} ·{" "}
                  {check.operation === "deploy"
                    ? "Deployment"
                    : check.target === "web"
                      ? "Web package build"
                      : "Installer build"}{" "}
                  · {check.status}
                  {check.duration !== undefined && ` · ${check.duration}s`}
                </p>
              )}
              {(error || query.error || report?.error) && (
                <p role="alert" className="release-error">
                  {error ||
                    (query.error instanceof Error ? query.error.message : "") ||
                    report?.error}
                </p>
              )}
              {(check?.output || check?.live_output) && (
                <details open={running || report?.state === "error"}>
                  <summary>Build and deployment log</summary>
                  <pre className="release-log">
                    {[check.output, check.live_output].filter(Boolean).join("\n")}
                  </pre>
                </details>
              )}
              {completed &&
                report?.urls
                  ?.filter((url) => /^https:\/\//.test(url))
                  .map((url) => (
                    <a
                      className="release-url"
                      key={url}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <ExternalLinkIcon size={15} />
                      {url}
                    </a>
                  ))}
              {completed && (
                <div className="release-artifacts">
                  {report?.artifacts
                    ?.filter(
                      (artifact) =>
                        check?.target === target &&
                        (mode === "deploy" || target === "web" || artifact.installable),
                    )
                    .map((artifact) => (
                      <article key={artifact.name}>
                        <strong>{artifact.name}</strong>
                        <span>{(artifact.bytes / 1024 / 1024).toFixed(2)} MB</span>
                        <code title="SHA-256">SHA-256: {artifact.sha256}</code>
                        <button
                          type="button"
                          disabled={!!downloading || busy || running || !!report.source_changed}
                          onClick={() => void download(artifact)}
                        >
                          <DownloadIcon size={15} />
                          {downloading === artifact.name ? "Downloading…" : "Download package"}
                        </button>
                      </article>
                    ))}
                </div>
              )}
              {report?.source_changed && (
                <p role="status">
                  Project source changed. Build again to download or deploy its latest version.
                </p>
              )}
              <button
                type="button"
                disabled={busy || running || query.isFetching}
                onClick={() => void query.refetch()}
              >
                Check readiness
              </button>
              {report && (
                <button type="button" onClick={downloadReport}>
                  <DownloadIcon size={15} /> Download report
                </button>
              )}
            </section>
          </div>
          <p className="preproduction-notice release-notice">
            {report?.notice ??
              "Compatible browser frontends can be converted into platform wrappers. Server logic and native-only features need an appropriate project build workflow."}
          </p>
        </>
      )}
    </PageScroll>
  );
}

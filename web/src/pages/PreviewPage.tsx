/* oxlint-disable react/iframe-missing-sandbox -- Preview endpoints are discovered from the job runtime on a separate port; scripts and storage are required to test the app. */
import { useLayoutEffect, useRef, useState } from "react";
import {
  ExternalLinkIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  LockKeyholeIcon,
  GlobeIcon,
  BatteryFullIcon,
  WifiIcon,
  SignalIcon,
  Maximize2Icon,
  Minimize2Icon,
  MinusIcon,
  MonitorIcon,
  RotateCwIcon,
  SmartphoneIcon,
  XIcon,
} from "lucide-react";
import { useSearchParams, Link } from "@/lib/routing";
import { useProjectSessions } from "@/hooks/useConversations";
import { useProjectPreview } from "@/hooks/useProjectPreview";
import { PageScroll } from "@/components/PageScroll";
import { PeriscopeIcon } from "@/components/icons/PeriscopeIcon";
import {
  PreviewChangeRequest,
  PreviewSelectButton,
  PreviewSelectionOverlay,
  usePreviewSelection,
} from "./PreviewSelection";
import "./preview.css";

const DEVICES = [
  { id: "android", name: "Android", width: 412, height: 915 },
  { id: "ios", name: "iOS", width: 393, height: 852 },
  { id: "web", name: "Web", width: 1440, height: 900 },
] as const;
type Device = (typeof DEVICES)[number];

function PreviewPanel({
  device,
  sessionId,
  url,
  revision,
  revisionQuery,
  maximized,
  hidden,
  onMaximize,
  onClose,
}: {
  device: Device;
  sessionId: string | null;
  url: string | null;
  revision: string;
  revisionQuery: boolean;
  maximized: boolean;
  hidden: boolean;
  onMaximize: () => void;
  onClose: () => void;
}) {
  const [minimized, setMinimized] = useState(false);
  const [reload, setReload] = useState(0);
  const [rotated, setRotated] = useState(false);
  const [availableWidth, setAvailableWidth] = useState(0);
  const stage = useRef<HTMLDivElement>(null);
  const width = rotated ? device.height : device.width;
  const height = rotated ? device.width : device.height;
  const frameUrl = url ? new URL(url) : null;
  // Static servers may round Last-Modified to a second; distinct revisions
  // must bypass conditional caches even when edits happen within that second.
  if (revisionQuery) {
    frameUrl?.searchParams.set("__xwav_preview_revision", `${revision}:${reload}`);
  }
  const selectionContext = `${revision}:${reload}:${url}:${width}:${height}`;
  const selection = usePreviewSelection(selectionContext);
  const phone = device.id !== "web";
  const bezel = phone ? 12 : 0;
  const topBar = phone ? 44 : 96;
  const bottomBar = phone ? 34 : 30;
  const frameWidth = width + bezel * 2 + (phone ? 4 : 2);
  const frameHeight = height + bezel * 2 + topBar + bottomBar + (phone ? 4 : 2);
  const scale = Math.max(0, Math.min(1, (availableWidth - (phone ? 24 : 0)) / frameWidth));
  useLayoutEffect(() => {
    const node = stage.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) => setAvailableWidth(entry.contentRect.width));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return (
    <section
      aria-label={`${device.name} preview panel`}
      className={`preview-panel preview-panel-${device.id} ${maximized ? "preview-panel-maximized" : ""}`}
      hidden={hidden}
    >
      <header className="preview-panel-header">
        <div className="preview-device-name">
          {device.id === "web" ? <MonitorIcon size={16} /> : <SmartphoneIcon size={16} />}
          <h2>{device.name}</h2>
          <span>
            {width} × {height}
          </span>
        </div>
        <div className="preview-window-actions">
          <PreviewSelectButton
            device={device.name}
            disabled={!url || !sessionId}
            selection={selection}
          />
          {device.id !== "web" && (
            <button
              type="button"
              disabled={selection.sending}
              title="Rotate viewport"
              aria-label={`Rotate ${device.name}`}
              onClick={() => setRotated(!rotated)}
            >
              <RotateCwIcon size={15} />
            </button>
          )}
          <button
            type="button"
            title={minimized ? "Restore preview" : "Minimize preview"}
            aria-label={`${minimized ? "Restore" : "Minimize"} ${device.name}`}
            onClick={() => setMinimized(!minimized)}
          >
            {minimized ? <Maximize2Icon size={15} /> : <MinusIcon size={15} />}
          </button>
          <button
            type="button"
            title={maximized ? "Restore panel size" : "Maximize panel"}
            aria-label={`${maximized ? "Unmaximize" : "Maximize"} ${device.name}`}
            onClick={() => {
              setMinimized(false);
              onMaximize();
            }}
          >
            {maximized ? <Minimize2Icon size={15} /> : <Maximize2Icon size={15} />}
          </button>
          <button
            type="button"
            title="Close preview and release its resources"
            aria-label={`Close ${device.name}`}
            onClick={onClose}
          >
            <XIcon size={15} />
          </button>
        </div>
      </header>
      <div className="preview-stage" ref={stage} hidden={minimized}>
        <div
          className="preview-device-fit"
          style={{ width: frameWidth * scale, height: frameHeight * scale }}
        >
          <div
            className={`preview-device-shell preview-device-${device.id} ${rotated ? "preview-device-landscape" : ""}`}
            data-testid={`preview-device-${device.id}`}
            style={{
              width: frameWidth,
              height: frameHeight,
              padding: bezel,
              transform: `scale(${scale})`,
            }}
          >
            {phone ? (
              <div className="preview-device-topbar" style={{ height: topBar }} aria-hidden="true">
                <span className="preview-device-time">9:41</span>
                <span
                  className={device.id === "ios" ? "preview-dynamic-island" : "preview-punch-hole"}
                />
                <span className="preview-device-signals">
                  <SignalIcon size={17} />
                  <WifiIcon size={17} />
                  <BatteryFullIcon size={23} />
                </span>
              </div>
            ) : (
              <div className="preview-browser-chrome" style={{ height: topBar }}>
                <div className="preview-browser-tabstrip" aria-hidden="true">
                  <span className="preview-browser-dots">
                    <i />
                    <i />
                    <i />
                  </span>
                  <span className="preview-browser-tab">
                    <GlobeIcon size={16} /> Xwav · Project preview <XIcon size={13} />
                  </span>
                  <span className="preview-browser-newtab">+</span>
                </div>
                <div className="preview-browser-toolbar">
                  <span className="preview-browser-history" aria-hidden="true">
                    <ArrowLeftIcon size={19} />
                    <ArrowRightIcon size={19} />
                  </span>
                  <button
                    type="button"
                    aria-label="Reload Web app"
                    title="Reload the live web app"
                    disabled={!url || selection.sending}
                    onClick={() => setReload((value) => value + 1)}
                  >
                    <RotateCwIcon size={18} />
                  </button>
                  <span className="preview-browser-address">
                    <LockKeyholeIcon size={15} />
                    <span>{url ?? "Your project’s live app will appear here"}</span>
                  </span>
                  {url && (
                    <a
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label="Open Web app in new tab"
                      title="Open app in a full browser tab"
                    >
                      <ExternalLinkIcon size={18} />
                    </a>
                  )}
                </div>
              </div>
            )}
            <div className="preview-device-screen" style={{ width, height }}>
              {url ? (
                <iframe
                  key={`${revision}:${reload}`}
                  title={`${device.name} app preview`}
                  src={frameUrl!.href}
                  width={width}
                  height={height}
                  sandbox="allow-scripts allow-same-origin allow-forms allow-modals allow-popups allow-downloads"
                  onLoad={() => {
                    selection.setRegion(null);
                    selection.setSelecting(false);
                  }}
                  referrerPolicy="no-referrer"
                />
              ) : (
                <div
                  className={`preview-device-idle preview-idle-${device.id}`}
                  role="img"
                  aria-label={`${device.name} preview standby screen`}
                >
                  {!phone && (
                    <div className="preview-web-standby-header">
                      <span>XWAV / LIVE PREVIEW</span>
                      <span className="preview-web-standby-badge">Ready to connect</span>
                    </div>
                  )}
                  {phone && (
                    <div className="preview-idle-clock" aria-hidden="true">
                      {device.id === "android" ? (
                        <>
                          <span>09</span>
                          <span>41</span>
                        </>
                      ) : (
                        <>
                          <strong>9:41</strong>
                          <span>Ready for your next idea</span>
                        </>
                      )}
                    </div>
                  )}
                  <div className="preview-idle-app">
                    <span className="preview-idle-app-icon">
                      <PeriscopeIcon />
                    </span>
                    <h3>Your app, right here.</h3>
                    <p>Waiting for this job’s live {device.name} app…</p>
                    <span className="preview-idle-caption">Ready for your Xwav project</span>
                  </div>
                  {phone && (
                    <div className="preview-idle-dock" aria-hidden="true">
                      <i />
                      <i />
                      <i />
                      <i />
                    </div>
                  )}
                </div>
              )}
              {url && (
                <PreviewSelectionOverlay
                  device={device.name}
                  width={width}
                  height={height}
                  selection={selection}
                />
              )}
            </div>
            {!phone && (
              <div className="preview-browser-status" style={{ height: bottomBar }}>
                <span>
                  <i />
                  {url ? "Connected to project runtime" : "Standby · waiting for your app"}
                </span>
                <span>
                  {width} × {height} · Web viewport
                </span>
              </div>
            )}
            {phone && (
              <div
                className="preview-device-navigation"
                style={{ height: bottomBar }}
                aria-hidden="true"
              >
                {device.id === "ios" ? (
                  <span className="preview-home-indicator" />
                ) : (
                  <>
                    <span className="preview-android-back" />
                    <span className="preview-android-home" />
                    <span className="preview-android-overview" />
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
      <div hidden={minimized}>
        <PreviewChangeRequest
          sessionId={sessionId}
          device={device.name}
          url={url}
          width={width}
          height={height}
          context={selectionContext}
          selection={selection}
        />
      </div>
      {minimized && (
        <button type="button" className="preview-minimized" onClick={() => setMinimized(false)}>
          Restore {device.name} preview
        </button>
      )}
    </section>
  );
}

export function PreviewPage() {
  const [params] = useSearchParams();
  const project = params.get("project") ?? "";
  const requestedSession = params.get("session");
  const jobs = useProjectSessions(project, !requestedSession && !!project);
  const sessionId = requestedSession ?? jobs.data?.pages[0]?.data[0]?.id ?? null;
  const preview = useProjectPreview(sessionId);
  const status = preview.data;
  const localServer = ["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname);
  const url =
    localServer &&
    status?.state === "ready" &&
    status.port &&
    status.port > 0 &&
    status.port <= 65535
      ? `http://127.0.0.1:${status.port}/`
      : null;
  const revision = `${sessionId}:${status?.version ?? ""}`;
  const [closed, setClosed] = useState<string[]>([]);
  const [maximized, setMaximized] = useState<string | null>(null);
  return (
    <PageScroll
      className="preview-page"
      maxWidthClassName="max-w-none"
      extraTop="clamp(20px, 3vw, 44px)"
    >
      <main>
        <header className="preview-page-heading">
          <div>
            <p className="preview-eyebrow">
              <PeriscopeIcon className="size-4" /> XWAV PREVIEW
            </p>
            <h1>See it in action.</h1>
            <p>One live job. Three perspectives. Keep this tab open while you build in Xwav.</p>
          </div>
        </header>
        <div className="preview-live-status" role="status">
          <span className={url ? "text-primary" : "text-muted-foreground"}>●</span>
          <p>
            {!sessionId
              ? project
                ? "This project needs a job with a workspace before it can be previewed."
                : "Open Preview from a project job’s input box to preview its app."
              : preview.isError
                ? "Waiting for this job’s runtime to reconnect…"
                : !localServer
                  ? "This remote runtime needs a published app endpoint before it can be previewed in your browser."
                  : (status?.message ?? "Connecting to this job’s workspace…")}
          </p>
          {sessionId && <Link to={`/c/${encodeURIComponent(sessionId)}`}>Back to job</Link>}
          {url && (
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Open app in browser"
              title="Open the live app in a full browser tab"
            >
              <ExternalLinkIcon size={18} />
            </a>
          )}
        </div>
        <p className="preview-help">
          Connected to this job’s actual web app, including while you work in another tab. Supported
          development servers update live; static pages refresh when their source changes. Android
          and iOS show responsive browser layouts, not native runtimes or device-specific browser
          engines. Select the crosshair on a panel, highlight an area, then describe the change to
          send it to this job.
        </p>
        <div className="preview-panel-toggles" aria-label="Preview devices">
          {DEVICES.map((device) => (
            <button
              key={device.id}
              type="button"
              aria-pressed={!closed.includes(device.id)}
              aria-label={`${closed.includes(device.id) ? "Reopen" : "Close"} ${device.name} preview`}
              onClick={() => {
                setClosed((previous) =>
                  previous.includes(device.id)
                    ? previous.filter((id) => id !== device.id)
                    : [...previous, device.id],
                );
                if (maximized === device.id) setMaximized(null);
              }}
            >
              {device.name}
              <span>{closed.includes(device.id) ? "Closed · reopen" : "Open"}</span>
            </button>
          ))}
        </div>
        <div className={`preview-panels ${maximized ? "preview-panels-focused" : ""}`}>
          {DEVICES.filter((device) => !closed.includes(device.id)).map((device) => (
            <PreviewPanel
              key={`${sessionId}:${device.id}`}
              device={device}
              sessionId={sessionId}
              url={url}
              revision={revision}
              revisionQuery={status?.revision_query !== false}
              maximized={maximized === device.id}
              hidden={maximized !== null && maximized !== device.id}
              onMaximize={() => setMaximized(maximized === device.id ? null : device.id)}
              onClose={() => {
                setClosed((previous) => [...previous, device.id]);
                if (maximized === device.id) setMaximized(null);
              }}
            />
          ))}
        </div>
        {closed.length === DEVICES.length && (
          <p className="preview-help" role="status">
            All previews are closed. Choose a device above to reopen it.
          </p>
        )}
      </main>
    </PageScroll>
  );
}

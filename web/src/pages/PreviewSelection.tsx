import { useEffect, useLayoutEffect, useRef, useState, type PointerEvent } from "react";
import { CrosshairIcon, SendIcon, XIcon } from "lucide-react";
import { postEvent } from "@/lib/sessionsApi";

export interface PreviewRegion {
  x: number;
  y: number;
  width: number;
  height: number;
}

export function previewRegion(
  start: { x: number; y: number },
  end: { x: number; y: number },
): PreviewRegion {
  return {
    x: Math.round(Math.min(start.x, end.x)),
    y: Math.round(Math.min(start.y, end.y)),
    width: Math.max(1, Math.round(Math.abs(end.x - start.x))),
    height: Math.max(1, Math.round(Math.abs(end.y - start.y))),
  };
}

export function usePreviewSelection(context: string) {
  const [selecting, setSelecting] = useState(false);
  const [sending, setSending] = useState(false);
  const [region, setRegion] = useState<PreviewRegion | null>(null);
  useEffect(() => {
    setSelecting(false);
    setSending(false);
    setRegion(null);
  }, [context]);
  return { selecting, setSelecting, region, setRegion, sending, setSending };
}

export function previewPointerPoint(
  clientX: number,
  clientY: number,
  bounds: { left: number; top: number; width: number; height: number },
  width: number,
  height: number,
) {
  return {
    x: Math.max(0, Math.min(width, ((clientX - bounds.left) * width) / bounds.width)),
    y: Math.max(0, Math.min(height, ((clientY - bounds.top) * height) / bounds.height)),
  };
}

export function clampPreviewRegion(
  region: PreviewRegion,
  width: number,
  height: number,
): PreviewRegion {
  const x = Math.max(0, Math.min(width - 1, Math.round(region.x)));
  const y = Math.max(0, Math.min(height - 1, Math.round(region.y)));
  return {
    x,
    y,
    width: Math.max(1, Math.min(width - x, Math.round(region.width))),
    height: Math.max(1, Math.min(height - y, Math.round(region.height))),
  };
}

export function PreviewSelectionOverlay({
  device,
  width,
  height,
  selection,
}: {
  device: string;
  width: number;
  height: number;
  selection: ReturnType<typeof usePreviewSelection>;
}) {
  const { selecting, setSelecting, region, setRegion } = selection;
  const surface = useRef<HTMLButtonElement>(null);
  const outline = useRef<HTMLDivElement>(null);
  const gesture = useRef<{
    pointerId: number;
    start: { x: number; y: number };
    bounds: DOMRect;
    dirty: boolean;
  } | null>(null);
  const draft = useRef<PreviewRegion | null>(null);
  const frame = useRef<number | null>(null);
  function stopFrame() {
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    frame.current = null;
  }
  function paint() {
    frame.current = null;
    const node = outline.current;
    const value = draft.current;
    if (!node || !value) return;
    node.hidden = false;
    node.style.transform = `translate3d(${value.x}px, ${value.y}px, 0)`;
    node.style.width = `${value.width}px`;
    node.style.height = `${value.height}px`;
    node.dataset.point = String(value.width === 1 && value.height === 1);
  }
  function updateDraft(value: PreviewRegion) {
    draft.current = clampPreviewRegion(value, width, height);
    if (frame.current === null) frame.current = requestAnimationFrame(paint);
  }
  useLayoutEffect(() => {
    if (!selecting) return;
    surface.current?.focus({ preventScroll: true });
    draft.current = null;
    function invalidateBounds() {
      if (gesture.current) gesture.current.dirty = true;
    }
    window.addEventListener("scroll", invalidateBounds, true);
    window.addEventListener("resize", invalidateBounds);
    const observer = new ResizeObserver(invalidateBounds);
    const stage = surface.current?.closest(".preview-stage");
    if (stage) observer.observe(stage);
    return () => {
      window.removeEventListener("scroll", invalidateBounds, true);
      window.removeEventListener("resize", invalidateBounds);
      observer.disconnect();
      gesture.current = null;
      // Cancel the pending frame without reading refs during effect cleanup.
      stopFrame();
    };
  }, [selecting]);
  function point(event: PointerEvent<HTMLButtonElement>, fresh = false) {
    const active = gesture.current!;
    if (fresh || active.dirty) {
      const next = event.currentTarget.getBoundingClientRect();
      if (next.width > 0 && next.height > 0) active.bounds = next;
      active.dirty = false;
    }
    return previewPointerPoint(event.clientX, event.clientY, active.bounds, width, height);
  }
  function cancel() {
    gesture.current = null;
    draft.current = null;
    stopFrame();
    setRegion(null);
    setSelecting(false);
  }
  return (
    <>
      {selecting && (
        <>
          <button
            type="button"
            className="preview-selection-surface"
            aria-label={`Select area in ${device} preview`}
            title="Drag a precise region or click a point. Arrow keys move; Shift+arrows resize. Enter confirms; Escape cancels."
            ref={surface}
            onPointerDown={(event) => {
              if (event.button !== 0 || gesture.current) return;
              event.preventDefault();
              const bounds = event.currentTarget.getBoundingClientRect();
              if (bounds.width <= 0 || bounds.height <= 0) return;
              event.currentTarget.setPointerCapture(event.pointerId);
              const start = previewPointerPoint(
                event.clientX,
                event.clientY,
                bounds,
                width,
                height,
              );
              gesture.current = { pointerId: event.pointerId, start, bounds, dirty: false };
              updateDraft(previewRegion(start, start));
            }}
            onPointerMove={(event) => {
              const active = gesture.current;
              if (active && active.pointerId === event.pointerId)
                updateDraft(previewRegion(active.start, point(event)));
            }}
            onPointerUp={(event) => {
              const active = gesture.current;
              if (!active || active.pointerId !== event.pointerId) return;
              const result = clampPreviewRegion(
                previewRegion(active.start, point(event, true)),
                width,
                height,
              );
              gesture.current = null;
              stopFrame();
              setRegion(result);
              setSelecting(false);
            }}
            onPointerCancel={(event) => {
              if (gesture.current?.pointerId === event.pointerId) cancel();
            }}
            onLostPointerCapture={(event) => {
              if (gesture.current?.pointerId === event.pointerId) cancel();
            }}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault();
                cancel();
                return;
              }
              if (gesture.current) return;
              const current = draft.current ?? {
                x: Math.floor(width / 2),
                y: Math.floor(height / 2),
                width: 1,
                height: 1,
              };
              if (event.key.startsWith("Arrow")) {
                event.preventDefault();
                const dx = event.key === "ArrowLeft" ? -1 : event.key === "ArrowRight" ? 1 : 0;
                const dy = event.key === "ArrowUp" ? -1 : event.key === "ArrowDown" ? 1 : 0;
                updateDraft(
                  event.shiftKey
                    ? { ...current, width: current.width + dx, height: current.height + dy }
                    : { ...current, x: current.x + dx, y: current.y + dy },
                );
              }
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                stopFrame();
                setRegion(clampPreviewRegion(current, width, height));
                setSelecting(false);
              }
            }}
          />
          <div
            ref={outline}
            hidden
            className="preview-selection-highlight preview-selection-draft"
            data-testid={`preview-selection-draft-${device.toLowerCase()}`}
          />
        </>
      )}
      {!selecting && region && (
        <div
          className="preview-selection-highlight"
          data-point={region.width === 1 && region.height === 1}
          data-testid={`preview-selection-${device.toLowerCase()}`}
          style={{ left: region.x, top: region.y, width: region.width, height: region.height }}
        />
      )}
    </>
  );
}

export function PreviewSelectButton({
  device,
  disabled,
  selection,
}: {
  device: string;
  disabled: boolean;
  selection: ReturnType<typeof usePreviewSelection>;
}) {
  return (
    <button
      type="button"
      disabled={disabled || selection.sending}
      aria-pressed={selection.selecting}
      aria-label={`Select area in ${device}`}
      title="Select a visible area and ask the job to change it"
      onClick={() => {
        selection.setRegion(null);
        selection.setSelecting(!selection.selecting);
      }}
    >
      <CrosshairIcon size={15} />
    </button>
  );
}

export function PreviewChangeRequest({
  sessionId,
  device,
  url,
  width,
  height,
  context,
  selection,
}: {
  sessionId: string | null;
  device: string;
  url: string | null;
  width: number;
  height: number;
  context: string;
  selection: ReturnType<typeof usePreviewSelection>;
}) {
  const [text, setText] = useState("");
  const busy = selection.sending;
  const setBusy = selection.setSending;
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const input = useRef<HTMLTextAreaElement>(null);
  const generation = useRef(0);
  const inFlight = useRef(false);
  const retry = useRef<{ content: string; id: string } | null>(null);
  useEffect(() => {
    generation.current++;
    setError("");
    setSent(false);
    setBusy(false);
    inFlight.current = false;
    const invalidate = () => {
      generation.current += 1;
    };
    return invalidate;
  }, [context, setBusy]);
  useEffect(() => {
    if (selection.region && !selection.selecting) {
      setSent(false);
      setError("");
      if (document.activeElement?.tagName !== "INPUT")
        input.current?.focus({ preventScroll: true });
    }
  }, [selection.region, selection.selecting]);
  const region = selection.region;
  if (selection.selecting)
    return (
      <p className="preview-selection-help" role="status">
        Drag over {device} to highlight an exact area, or click a point. Arrow keys move by one
        pixel; Shift+arrows resize. Enter confirms; Escape cancels.
      </p>
    );
  if (!region)
    return text ? (
      <p className="preview-selection-help">Your draft is saved. Select an area to send it.</p>
    ) : null;
  async function send() {
    if (!sessionId || !url || !region || !text.trim() || inFlight.current) return;
    const current = generation.current;
    const content = `Please update the shared app in this job based on this preview selection.\nApply the requested change consistently across Web, Android, and iOS previews. The selected device identifies the target area, not the scope of the change. Update shared source, components, styles, and behavior so all three views reflect the change while preserving their appropriate responsive layouts. Check the result at all three viewport sizes; do not create separate device copies or limit the update to the selected viewport.\n\nDevice: ${device} responsive web preview\nPreview entry URL: ${url}\nViewport: ${width} × ${height} CSS pixels\nSelected visible region: x=${region.x}, y=${region.y}, width=${region.width}, height=${region.height} CSS pixels, relative to the top-left of the visible viewport.\nThis is a visual region, not a DOM selector; no screenshot is attached. Use the description and inspect the app/source to identify the target.\n\nRequested change:\n${text.trim()}`;
    if (retry.current?.content !== content)
      retry.current = { content, id: crypto.randomUUID().replaceAll("-", "") };
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await postEvent(sessionId, {
        type: "message",
        data: {
          role: "user",
          content: [{ type: "input_text", text: content }],
          stable_id: retry.current.id,
        },
      });
      if (result.denied)
        throw new Error("This job’s policy did not allow the request. Your draft is kept.");
      if (current !== generation.current) return;
      setText("");
      setSent(true);
      retry.current = null;
    } catch (failure) {
      if (current === generation.current)
        setError(
          failure instanceof Error
            ? failure.message
            : "Could not send. Your draft is kept; try again.",
        );
    } finally {
      if (current === generation.current) {
        setBusy(false);
        inFlight.current = false;
      }
    }
  }
  return (
    <form
      className="preview-change-request"
      aria-label={`${device} change request`}
      onSubmit={(event) => {
        event.preventDefault();
        void send();
      }}
    >
      <div className="preview-change-heading">
        <strong>{device} · Selected area</strong>
        <button
          type="button"
          aria-label={`Clear ${device} selection`}
          disabled={busy}
          onClick={() => selection.setRegion(null)}
        >
          <XIcon size={16} />
        </button>
      </div>
      <p>
        {region.width} × {region.height} at ({region.x}, {region.y}) · Applies across Web, Android,
        and iOS
      </p>
      {!sent && (
        <fieldset className="preview-selection-coordinates" disabled={busy}>
          <legend>Refine selection · CSS pixels</legend>
          {(["x", "y", "width", "height"] as const).map((axis) => (
            <label key={axis}>
              {axis === "x" || axis === "y"
                ? axis.toUpperCase()
                : axis === "width"
                  ? "Width"
                  : "Height"}
              <input
                type="number"
                aria-label={`${device} selection ${axis}`}
                min={axis === "x" || axis === "y" ? 0 : 1}
                max={
                  axis === "x"
                    ? width - 1
                    : axis === "y"
                      ? height - 1
                      : axis === "width"
                        ? width - region.x
                        : height - region.y
                }
                step={1}
                value={region[axis]}
                onChange={(event) => {
                  const value = event.currentTarget.valueAsNumber;
                  if (Number.isFinite(value))
                    selection.setRegion(
                      clampPreviewRegion({ ...region, [axis]: value }, width, height),
                    );
                }}
              />
            </label>
          ))}
        </fieldset>
      )}
      {sent ? (
        <p role="status">
          Request sent to the job for Web, Android, and iOS. All live previews update as the shared
          app changes.
        </p>
      ) : (
        <>
          <label htmlFor={`preview-change-${device}`}>What should change in this area?</label>
          <textarea
            id={`preview-change-${device}`}
            ref={input}
            value={text}
            maxLength={12000}
            rows={3}
            disabled={busy}
            placeholder="For example: make this button larger and use our brand color…"
            onChange={(event) => setText(event.target.value)}
          />
          {error && <p role="alert">{error}</p>}
          <button
            className="preview-change-send"
            type="submit"
            disabled={busy || !text.trim() || !sessionId}
          >
            <SendIcon size={15} />
            {busy ? "Sending…" : "Request change"}
          </button>
        </>
      )}
    </form>
  );
}

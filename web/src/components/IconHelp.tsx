import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { getEmbedRoot } from "@/lib/host";
import { placeTooltip } from "@/shell/useCursorTooltip";

const CONTROLS = "button, a[href], [role=button], [role=tab], [role=menuitem], summary";

function iconControl(target: EventTarget | null): HTMLElement | null {
  if (!(target instanceof Element)) return null;
  const control = target.closest<HTMLElement>(CONTROLS);
  if (!control?.querySelector("svg") || control.closest("[data-slot=tooltip-trigger]")) return null;
  return control;
}

function description(control: HTMLElement): string {
  const labelledBy = control
    .getAttribute("aria-labelledby")
    ?.split(/\s+/)
    .map((id) => document.getElementById(id)?.textContent ?? "")
    .join(" ");
  return (
    control.getAttribute("data-icon-help") ||
    control.getAttribute("title") ||
    control.getAttribute("aria-description") ||
    control.getAttribute("aria-label") ||
    labelledBy ||
    control.textContent ||
    ""
  )
    .trim()
    .slice(0, 240);
}

/** One delegated, lazily shown fallback for icons without a dedicated tooltip. */
export function IconHelp() {
  const id = useId();
  const popup = useRef<HTMLDivElement>(null);
  const dismiss = useRef<() => void>(() => {});
  const leaveTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const [help, setHelp] = useState<{ text: string; control: HTMLElement } | null>(null);
  const [position, setPosition] = useState({ left: 8, top: 8, maxWidth: 280 });

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let active: HTMLElement | null = null;
    let suppressedTitle: string | null = null;
    let addedLabel: string | null = null;
    let pointerFocus = false;
    const root = getEmbedRoot() ?? document.body;
    function hide() {
      clearTimeout(timer);
      clearTimeout(leaveTimer.current);
      if (active) {
        if (suppressedTitle !== null && !active.hasAttribute("title"))
          active.setAttribute("title", suppressedTitle);
        const ids = (active.getAttribute("aria-describedby") ?? "")
          .split(/\s+/)
          .filter((value) => value && value !== id);
        if (ids.length) active.setAttribute("aria-describedby", ids.join(" "));
        else active.removeAttribute("aria-describedby");
        if (addedLabel && active.getAttribute("aria-label") === addedLabel)
          active.removeAttribute("aria-label");
      }
      active = null;
      suppressedTitle = null;
      addedLabel = null;
      setHelp(null);
    }
    dismiss.current = hide;
    function show(control: HTMLElement, delay: number) {
      clearTimeout(leaveTimer.current);
      if (!root.contains(control) || active === control) return;
      hide();
      const text = description(control);
      if (!text) return;
      active = control;
      timer = setTimeout(() => {
        if (!control.isConnected || active !== control) return;
        suppressedTitle = control.getAttribute("title");
        if (
          !control.hasAttribute("aria-label") &&
          !control.hasAttribute("aria-labelledby") &&
          !control.textContent?.trim()
        ) {
          addedLabel = text;
          control.setAttribute("aria-label", text);
        }
        control.removeAttribute("title");
        const ids = (control.getAttribute("aria-describedby") ?? "").split(/\s+/).filter(Boolean);
        control.setAttribute("aria-describedby", [...ids, id].join(" "));
        setHelp({ text, control });
      }, delay);
    }
    function hover(event: PointerEvent) {
      if (event.pointerType === "touch") return;
      const control = iconControl(event.target);
      if (control) show(control, 350);
    }
    function leave(event: PointerEvent) {
      const related = event.relatedTarget instanceof Node ? event.relatedTarget : null;
      if (
        active?.contains(event.target as Node) &&
        !active.contains(related) &&
        !popup.current?.contains(related)
      )
        leaveTimer.current = setTimeout(hide, 150);
    }
    function focus(event: FocusEvent) {
      if (pointerFocus) return;
      const control = iconControl(event.target);
      if (control) show(control, 100);
    }
    function blur(event: FocusEvent) {
      if (active?.contains(event.target as Node)) hide();
    }
    function escape(event: KeyboardEvent) {
      pointerFocus = false;
      if (event.key === "Escape") hide();
    }
    function pointerDown() {
      pointerFocus = true;
      hide();
    }
    root.addEventListener("pointerover", hover);
    root.addEventListener("pointerout", leave);
    root.addEventListener("focusin", focus);
    root.addEventListener("focusout", blur);
    root.addEventListener("pointerdown", pointerDown, true);
    root.addEventListener("keydown", escape);
    root.addEventListener("scroll", hide, true);
    window.addEventListener("resize", hide);
    window.addEventListener("blur", hide);
    return () => {
      hide();
      root.removeEventListener("pointerover", hover);
      root.removeEventListener("pointerout", leave);
      root.removeEventListener("focusin", focus);
      root.removeEventListener("focusout", blur);
      root.removeEventListener("pointerdown", pointerDown, true);
      root.removeEventListener("keydown", escape);
      root.removeEventListener("scroll", hide, true);
      window.removeEventListener("resize", hide);
      window.removeEventListener("blur", hide);
    };
  }, [id]);

  useLayoutEffect(() => {
    if (!help || !popup.current) return;
    const anchor = help.control.getBoundingClientRect();
    const size = popup.current.getBoundingClientRect();
    setPosition(placeTooltip({ x: anchor.left, y: anchor.bottom }, size));
  }, [help]);

  return help
    ? createPortal(
        <div
          id={id}
          ref={popup}
          role="tooltip"
          className="xwav-icon-help"
          style={{ position: "fixed", ...position }}
          onPointerEnter={() => clearTimeout(leaveTimer.current)}
          onPointerLeave={(event) => {
            const related = event.relatedTarget instanceof Node ? event.relatedTarget : null;
            if (!help.control.contains(related)) dismiss.current();
          }}
        >
          {help.text}
        </div>,
        getEmbedRoot() ?? document.body,
      )
    : null;
}

import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import {
  clampPreviewRegion,
  previewPointerPoint,
  previewRegion,
  PreviewSelectionOverlay,
  type PreviewRegion,
} from "./PreviewSelection";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Preview region coordinates", () => {
  it("normalizes reverse drags and rounds CSS pixels", () => {
    expect(previewRegion({ x: 200.2, y: 130.3 }, { x: 12.4, y: 20.1 })).toEqual({
      x: 12,
      y: 20,
      width: 188,
      height: 110,
    });
  });
  it("keeps a point selection nonempty", () => {
    expect(previewRegion({ x: 0, y: 0 }, { x: 0, y: 0 })).toEqual({
      x: 0,
      y: 0,
      width: 1,
      height: 1,
    });
  });
  describe.each([
    [1440, 900],
    [412, 915],
    [393, 852],
    [915, 412],
    [852, 393],
  ])("viewport %s × %s", (width, height) => {
    it.each([0.125, 0.25, 0.7, 1, 1.5])("maps fractional positions at scale %s", (scale) => {
      const bounds = { left: 123.25, top: -85.5, width: width * scale, height: height * scale };
      const x = width * 0.37125;
      const y = height * 0.2145;
      const point = previewPointerPoint(
        bounds.left + x * scale,
        bounds.top + y * scale,
        bounds,
        width,
        height,
      );
      expect(point.x).toBeCloseTo(x, 8);
      expect(point.y).toBeCloseTo(y, 8);
    });
  });
  it("clamps edges without growing past the viewport", () => {
    expect(
      previewPointerPoint(-100, 9999, { left: 0, top: 0, width: 100, height: 200 }, 412, 915),
    ).toEqual({ x: 0, y: 915 });
    expect(clampPreviewRegion({ x: 412, y: 915, width: 1, height: 1 }, 412, 915)).toEqual({
      x: 411,
      y: 914,
      width: 1,
      height: 1,
    });
    expect(clampPreviewRegion({ x: -10, y: 30, width: 9999, height: 9999 }, 412, 915)).toEqual({
      x: 0,
      y: 30,
      width: 412,
      height: 885,
    });
  });
});

function overlay(width = 1440, height = 900) {
  const commit = vi.fn();
  let renders = 0;
  function Harness() {
    renders++;
    const [selecting, setSelecting] = useState(true);
    const [region, setRegion] = useState<PreviewRegion | null>(null);
    return (
      <PreviewSelectionOverlay
        device="Web"
        width={width}
        height={height}
        selection={{
          selecting,
          setSelecting,
          region,
          setRegion(value) {
            commit(value);
            setRegion(value);
          },
          sending: false,
          setSending: vi.fn(),
        }}
      />
    );
  }
  vi.stubGlobal(
    "PointerEvent",
    class extends MouseEvent {
      pointerId: number;
      constructor(type: string, init: PointerEventInit) {
        super(type, init);
        this.pointerId = init.pointerId ?? 1;
      }
    },
  );
  let tick: FrameRequestCallback | null = null;
  const raf = vi.fn((callback: FrameRequestCallback) => {
    tick = callback;
    return 1;
  });
  vi.stubGlobal("requestAnimationFrame", raf);
  vi.stubGlobal(
    "cancelAnimationFrame",
    vi.fn(() => {
      tick = null;
    }),
  );
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
  render(<Harness />);
  const surface = screen.getByRole("button", { name: "Select area in Web preview" });
  Object.defineProperty(surface, "setPointerCapture", { value: vi.fn() });
  const bounds = { left: 100, top: 200, width: width / 4, height: height / 4 } as DOMRect;
  const measure = vi.spyOn(surface, "getBoundingClientRect").mockReturnValue(bounds);
  return {
    surface,
    commit,
    measure,
    bounds,
    raf,
    renders: () => renders,
    flush() {
      const callback = tick;
      tick = null;
      callback?.(0);
    },
  };
}

describe("Preview pointer selection", () => {
  it("coalesces high-rate moves into one paint without panel rerenders or repeated layout reads", () => {
    const test = overlay();
    const initialRenders = test.renders();
    fireEvent.pointerDown(test.surface, { pointerId: 1, button: 0, clientX: 110, clientY: 210 });
    for (let n = 0; n < 200; n++)
      fireEvent.pointerMove(test.surface, { pointerId: 1, clientX: 120 + n / 10, clientY: 230 });
    expect(test.commit).not.toHaveBeenCalled();
    expect(test.renders()).toBe(initialRenders);
    expect(test.measure).toHaveBeenCalledOnce();
    expect(test.raf).toHaveBeenCalledOnce();
    test.flush();
    expect(screen.getByTestId("preview-selection-draft-web")).not.toHaveAttribute("hidden");
    fireEvent.pointerUp(test.surface, { pointerId: 1, clientX: 140, clientY: 230 });
    expect(test.commit).toHaveBeenCalledOnce();
    expect(test.commit).toHaveBeenLastCalledWith({ x: 40, y: 40, width: 120, height: 80 });
    expect(test.measure).toHaveBeenCalledTimes(2);
  });
  it("preserves exact clicks and tiny reverse drags instead of inflating them", () => {
    const test = overlay();
    fireEvent.pointerDown(test.surface, { pointerId: 2, button: 0, clientX: 125, clientY: 225 });
    fireEvent.pointerUp(test.surface, { pointerId: 2, clientX: 125, clientY: 225 });
    expect(test.commit).toHaveBeenLastCalledWith({ x: 100, y: 100, width: 1, height: 1 });
    cleanup();
    const next = overlay();
    fireEvent.pointerDown(next.surface, {
      pointerId: 3,
      button: 0,
      clientX: 125.5,
      clientY: 225.5,
    });
    fireEvent.pointerUp(next.surface, { pointerId: 3, clientX: 125, clientY: 225 });
    expect(next.commit).toHaveBeenLastCalledWith({ x: 100, y: 100, width: 2, height: 2 });
  });
  it("ignores another pointer and cancels lost capture without committing a stale draft", () => {
    const test = overlay();
    fireEvent.pointerDown(test.surface, { pointerId: 1, button: 0, clientX: 110, clientY: 210 });
    fireEvent.pointerUp(test.surface, { pointerId: 2, clientX: 200, clientY: 300 });
    expect(test.commit).not.toHaveBeenCalled();
    fireEvent.lostPointerCapture(test.surface, { pointerId: 1 });
    expect(test.commit).toHaveBeenLastCalledWith(null);
    expect(screen.queryByTestId("preview-selection-web")).toBeNull();
  });
  it("remeasures after scrolling and clamps a captured drag outside the frame", () => {
    const test = overlay(412, 915);
    fireEvent.pointerDown(test.surface, { pointerId: 1, button: 0, clientX: 110, clientY: 210 });
    test.measure.mockReturnValue({ ...test.bounds, top: 180 } as DOMRect);
    fireEvent.scroll(window);
    fireEvent.pointerMove(test.surface, { pointerId: 1, clientX: 1000, clientY: 1000 });
    fireEvent.pointerUp(test.surface, { pointerId: 1, clientX: 1000, clientY: 1000 });
    expect(test.commit).toHaveBeenLastCalledWith({ x: 40, y: 40, width: 372, height: 875 });
  });
  it("moves and resizes by single CSS pixels using the keyboard", () => {
    const test = overlay();
    fireEvent.keyDown(test.surface, { key: "ArrowRight" });
    fireEvent.keyDown(test.surface, { key: "ArrowDown", shiftKey: true });
    fireEvent.keyDown(test.surface, { key: "Enter" });
    expect(test.commit).toHaveBeenLastCalledWith({ x: 721, y: 450, width: 1, height: 2 });
  });
});

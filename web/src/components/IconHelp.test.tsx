import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { IconHelp } from "./IconHelp";
import { setEmbedRoot } from "@/lib/host";

beforeEach(() => {
  vi.useFakeTimers();
  vi.spyOn(document.documentElement, "clientWidth", "get").mockReturnValue(1000);
  vi.spyOn(document.documentElement, "clientHeight", "get").mockReturnValue(800);
});
afterEach(() => {
  cleanup();
  setEmbedRoot(null);
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function hover(button: HTMLElement) {
  fireEvent.pointerOver(button, { pointerType: "mouse" });
  act(() => vi.advanceTimersByTime(350));
}

it("describes titled icons, keeps their accessible name and restores native attributes", () => {
  render(
    <>
      <IconHelp />
      <button type="button" title="Open live previews">
        <svg />
      </button>
    </>,
  );
  const button = screen.getByRole("button", { name: "Open live previews" });
  hover(button);
  const tooltip = screen.getByRole("tooltip");
  expect(tooltip).toHaveTextContent("Open live previews");
  expect(button).toHaveAccessibleName("Open live previews");
  expect(button).toHaveAttribute("aria-describedby", tooltip.id);
  expect(button).not.toHaveAttribute("title");
  fireEvent.keyDown(button, { key: "Escape" });
  expect(screen.queryByRole("tooltip")).toBeNull();
  expect(button).toHaveAttribute("title", "Open live previews");
  expect(button).not.toHaveAttribute("aria-describedby");
  expect(button).not.toHaveAttribute("aria-label");
});

it("supports keyboard focus, preserves other descriptions and dismisses on blur", () => {
  render(
    <>
      <IconHelp />
      <p id="existing">Existing help</p>
      <button type="button" aria-label="Search" aria-describedby="existing">
        <svg />
      </button>
    </>,
  );
  const button = screen.getByRole("button", { name: "Search" });
  fireEvent.focusIn(button);
  act(() => vi.advanceTimersByTime(100));
  expect(screen.getByRole("tooltip")).toHaveTextContent("Search");
  expect(button.getAttribute("aria-describedby")).toContain("existing");
  fireEvent.focusOut(button);
  expect(button).toHaveAttribute("aria-describedby", "existing");
});

it("does not duplicate dedicated tooltips or describe decorative SVGs", () => {
  render(
    <>
      <IconHelp />
      <button type="button" data-slot="tooltip-trigger" aria-label="Existing tooltip">
        <svg />
      </button>
      <div data-testid="decoration">
        <svg />
      </div>
    </>,
  );
  hover(screen.getByRole("button"));
  expect(screen.queryByRole("tooltip")).toBeNull();
  hover(screen.getByTestId("decoration"));
  expect(screen.queryByRole("tooltip")).toBeNull();
});

it("does not show a focus tooltip after a pointer tap", () => {
  render(
    <>
      <IconHelp />
      <button type="button" aria-label="Settings">
        <svg />
      </button>
    </>,
  );
  const button = screen.getByRole("button");
  fireEvent.pointerDown(button);
  fireEvent.focusIn(button);
  act(() => vi.advanceTimersByTime(500));
  expect(screen.queryByRole("tooltip")).toBeNull();
  fireEvent.keyDown(button, { key: "Tab" });
  fireEvent.focusIn(button);
  act(() => vi.advanceTimersByTime(100));
  expect(screen.getByRole("tooltip")).toHaveTextContent("Settings");
});

it("lets a disabled icon explain its action without dispatching a click", () => {
  const click = vi.fn();
  render(
    <>
      <IconHelp />
      <button type="button" disabled aria-label="Send message" onClick={click}>
        <svg />
      </button>
    </>,
  );
  const button = screen.getByRole("button");
  hover(button);
  expect(screen.getByRole("tooltip")).toHaveTextContent("Send message");
  fireEvent.click(button);
  expect(click).not.toHaveBeenCalled();
});

it("keeps help hoverable and clears it when leaving the popup", () => {
  render(
    <>
      <IconHelp />
      <button type="button" aria-label="Settings">
        <svg />
      </button>
    </>,
  );
  const button = screen.getByRole("button");
  hover(button);
  fireEvent.pointerOut(button, { relatedTarget: document.body });
  fireEvent.pointerEnter(screen.getByRole("tooltip"));
  act(() => vi.advanceTimersByTime(200));
  expect(screen.getByRole("tooltip")).toBeVisible();
  fireEvent.pointerLeave(screen.getByRole("tooltip"), { relatedTarget: document.body });
  expect(screen.queryByRole("tooltip")).toBeNull();
  expect(button).not.toHaveAttribute("aria-describedby");
  hover(button);
  expect(screen.getByRole("tooltip")).toBeVisible();
});

it("handles late-added controls and scopes portals to the embedded app", () => {
  const scope = document.createElement("div");
  document.body.append(scope);
  setEmbedRoot(scope);
  const view = render(<IconHelp />, { container: scope });
  view.rerender(
    <>
      <IconHelp />
      <button type="button" aria-label="Download" data-icon-help="Download the project archive.">
        <svg />
      </button>
    </>,
  );
  hover(screen.getByRole("button", { name: "Download" }));
  expect(screen.getByRole("tooltip")).toHaveTextContent("Download the project archive.");
  expect(screen.getByRole("tooltip").parentElement).toBe(scope);
});

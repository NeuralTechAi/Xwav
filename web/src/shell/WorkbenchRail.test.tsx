import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { WorkbenchRail } from "./WorkbenchRail";

const theme = vi.hoisted(() => ({ resolvedTheme: "light", setTheme: vi.fn() }));
vi.mock("next-themes", () => ({ useTheme: () => theme }));
afterEach(() => {
  cleanup();
  theme.setTheme.mockClear();
  theme.resolvedTheme = "light";
});

function renderRail(path = "/") {
  const onSearch = vi.fn();
  render(
    <MemoryRouter initialEntries={[path]}>
      <WorkbenchRail onSearch={onSearch} />
      <Routes>
        <Route path="/settings/git" element={<p>Git configuration</p>} />
        <Route path="*" element={null} />
      </Routes>
    </MemoryRouter>,
  );
  return onSearch;
}

describe("Xwav workbench navigation", () => {
  it("navigates to the existing Git settings surface", () => {
    renderRail();
    expect(screen.getByRole("link", { name: "Workspace home" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    fireEvent.click(screen.getByRole("link", { name: "Git connections" }));
    expect(screen.getByText("Git configuration")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Git connections" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Workspace home" })).not.toHaveAttribute(
      "aria-current",
    );
  });
  it("opens the existing search action", () => {
    const onSearch = renderRail();
    fireEvent.click(screen.getByRole("button", { name: "Search workspace" }));
    expect(onSearch).toHaveBeenCalledOnce();
  });
  it.each([
    ["light", "Switch to dark mode", "dark"],
    ["dark", "Switch to light mode", "light"],
  ])("switches from %s using the shared theme provider", (current, label, target) => {
    theme.resolvedTheme = current;
    renderRail();
    fireEvent.click(screen.getByRole("button", { name: label }));
    expect(theme.setTheme).toHaveBeenCalledWith(target);
  });
  it("marks harness settings active and offers appearance", () => {
    renderRail("/settings/harnesses");
    expect(screen.getByRole("link", { name: "Harness settings" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Workbench appearance" })).toHaveAttribute(
      "href",
      "/settings/appearance",
    );
  });
});

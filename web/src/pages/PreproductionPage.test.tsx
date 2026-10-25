import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { PreproductionPage, reportDownload, type TestReport } from "./PreproductionPage";

vi.mock("@/hooks/useConversations", () => ({
  useProjectSessions: () => ({ data: { pages: [{ data: [] }] } }),
}));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const report: TestReport = {
  id: "run-one",
  state: "complete",
  notice: "Coverage gaps are not passes",
  checks: [
    {
      id: "1",
      category: "unit",
      platform: "shared",
      name: "Unit suite",
      status: "passed",
      duration: 1.2,
      output: "1 passed",
    },
    {
      id: "2",
      category: "security",
      platform: "shared",
      name: "Security scan",
      status: "failed",
      output: "Finding <script>alert(1)</script>",
    },
    {
      id: "3",
      category: "e2e",
      platform: "ios",
      name: "Native iOS suite",
      status: "blocked",
      reason: "Xcode required",
    },
  ],
};
function mount(path = "/preproduction?session=job-one", failed = false) {
  const fetch = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(report), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  // Each fetch needs an unread response body.
  fetch.mockImplementation(
    async () =>
      new Response(JSON.stringify(failed ? { detail: "Host offline" } : report), {
        status: failed ? 503 : 200,
      }),
  );
  vi.stubGlobal("fetch", fetch);
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[path]}>
        <PreproductionPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetch;
}

describe("Pre-production dashboard", () => {
  it("starts/loads only the current job and shows failures and coverage gaps", async () => {
    const fetch = mount();
    await waitFor(() => expect(screen.getByText("Failures need attention")).toBeVisible());
    expect(fetch.mock.calls[0][0]).toBe("/v1/sessions/job-one/preproduction");
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ action: "ensure" });
    expect(screen.getByText("Xcode required")).toBeVisible();
    expect(screen.getByRole("button", { name: "Download JSON" })).toBeEnabled();
    fireEvent.change(screen.getByRole("combobox", { name: "Filter test platform" }), {
      target: { value: "ios" },
    });
    expect(screen.getByRole("heading", { name: "Native iOS suite" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Unit suite" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Show all checks" }));
    expect(screen.getByRole("heading", { name: "Unit suite" })).toBeVisible();
  });
  it("does not run tests without a job", () => {
    const fetch = mount("/preproduction");
    expect(screen.getByText(/Open Pre-Production Tests from a project job/)).toBeVisible();
    expect(fetch).not.toHaveBeenCalled();
  });
  it("surfaces runtime errors without a passing dashboard", async () => {
    mount("/preproduction?session=job-one", true);
    await waitFor(() => expect(screen.getByRole("alert")).toBeVisible());
    expect(screen.queryByText("Configured checks passed")).toBeNull();
  });
  it("exports escaped HTML, complete JSON and safe CSV", () => {
    const html = reportDownload(report, "html");
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
    expect(JSON.parse(reportDownload(report, "json"))).toEqual(report);
    const formula = { ...report, checks: [{ ...report.checks[0], name: "=danger()" }] };
    expect(reportDownload(formula, "csv")).toContain('"\'=danger()"');
    expect(reportDownload(report, "csv")).toContain("blocked");
  });
});

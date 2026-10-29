import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { PenetrationPage } from "./PenetrationPage";

vi.mock("@/hooks/useConversations", () => ({
  useProjectSessions: () => ({ data: { pages: [{ data: [{ id: "project-job" }] }] } }),
}));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
const report = {
  state: "complete",
  runs: [{ id: "scan-one", updated_at: 1 }],
  run: { id: "scan-one", summary: "Scan review", mode: "quick" },
  strix_installed: false,
  counts: { high: 1, low: 1 },
  warnings: [],
  findings: [
    {
      id: "one",
      title: "Ownership check",
      severity: "high",
      validation: "reported",
      evidence: "GET /private",
      remediation_steps: "Validate ownership",
    },
    {
      id: "two",
      title: "Header check",
      severity: "low",
      validation: "verified",
      description: "Missing a header",
    },
  ],
};
function mount(path = "/penetration?session=job-one", data: unknown = report, failStart = false) {
  const fetch = vi.fn().mockImplementation(async () => Response.json(data));
  if (failStart)
    fetch.mockImplementationOnce(async () =>
      Response.json({ detail: "Model pool unavailable" }, { status: 503 }),
    );
  vi.stubGlobal("fetch", fetch);
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[path]}>
        <PenetrationPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetch;
}
it("starts the exact job automatically, displays evidence and filters severity", async () => {
  const fetch = mount();
  expect(await screen.findByText("Ownership check")).toBeVisible();
  expect(fetch.mock.calls[0][0]).toBe("/v1/sessions/job-one/penetration");
  expect(fetch.mock.calls[0][1].method).toBe("POST");
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ action: "start" });
  expect(screen.getByText(/optional Strix CLI is not installed/)).toBeVisible();
  expect(screen.getByText("GET /private")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Finding severity"), { target: { value: "high" } });
  expect(screen.queryByText("Header check")).not.toBeInTheDocument();
  expect(screen.getByText("Reported by Strix")).toBeVisible();
  fireEvent.change(screen.getByLabelText("Strix scan"), { target: { value: "scan-one" } });
  await waitFor(() => expect(fetch.mock.calls.at(-1)![0]).toContain("?run=scan-one"));
});
it("resolves project context and waits without any job", async () => {
  const fetch = mount("/penetration?project=Project+A");
  await waitFor(() => expect(fetch.mock.calls[0][0]).toBe("/v1/sessions/project-job/penetration"));
  cleanup();
  const none = mount("/penetration");
  expect(screen.getByRole("status")).toHaveTextContent("Open Penetration Test from a job");
  expect(none).not.toHaveBeenCalled();
});
it("shows missing reports without claiming a security pass", async () => {
  mount(undefined, { state: "empty", runs: [], findings: [], strix_installed: false });
  expect(await screen.findByText("No Strix reports yet")).toBeVisible();
  expect(screen.getByText(/No security pass is implied/)).toBeVisible();
});
it("downloads escaped findings with evidence", async () => {
  const blob = vi.fn().mockReturnValue("blob:test");
  vi.stubGlobal("URL", { createObjectURL: blob, revokeObjectURL: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  mount();
  await screen.findByText("Scan completed");
  fireEvent.click(screen.getByRole("button", { name: "Download JSON" }));
  const output = blob.mock.calls[0][0] as Blob;
  expect(await output.text()).toContain("Validate ownership");
});

it("Run again creates another scan rather than only reloading old results", async () => {
  const fetch = mount();
  await screen.findByText("Scan completed");
  fireEvent.click(screen.getByRole("button", { name: "Run again" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ action: "start" });
});
it("Stop scan cancels a running scan", async () => {
  const fetch = mount(undefined, { ...report, state: "running", managed: true });
  fireEvent.click(await screen.findByRole("button", { name: "Stop scan" }));
  await waitFor(() =>
    expect(JSON.parse(fetch.mock.calls.at(-1)![1].body)).toEqual({ action: "cancel" }),
  );
});

it("keeps historical links read-only", async () => {
  const fetch = mount("/penetration?session=job-one&run=scan-one");
  await screen.findByText("Scan completed");
  expect(fetch.mock.calls[0][0]).toContain("?run=scan-one");
  expect(fetch.mock.calls[0][1].method).toBeUndefined();
});
it("allows Run again to recover after automatic startup fails", async () => {
  const fetch = mount(undefined, report, true);
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Run again" }));
  expect(await screen.findByText("Scan completed")).toBeVisible();
  expect(JSON.parse(fetch.mock.calls.at(-1)![1].body)).toEqual({ action: "start" });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

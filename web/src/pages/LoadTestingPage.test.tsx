import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { LoadTestingPage } from "./LoadTestingPage";

vi.mock("@/hooks/useConversations", () => ({
  useProjectSessions: () => ({ data: { pages: [{ data: [{ id: "project-job" }] }] } }),
}));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
const report = {
  id: "run-a",
  state: "complete",
  checks: [
    {
      id: "load",
      name: "Load test",
      category: "load",
      platform: "shared",
      status: "passed",
      metrics: {
        requests: 12,
        errors: 0,
        error_percent: 0,
        rps: 6,
        p50_ms: 2,
        p95_ms: 5,
        p99_ms: 6,
        duration: 2,
        peak_concurrency: 2,
        platforms: { web: { requests: 4, errors: 0, p95_ms: 5 } },
        series: [{ second: 0, requests: 12, p95_ms: 5, errors: 0, concurrency: 2 }],
      },
      config: {
        durations: { load: 2 },
        max_requests: 100,
        requests_per_second: 10,
        max_p95_ms: 1000,
        max_error_percent: 1,
      },
    },
    {
      id: "stress",
      name: "Stress test",
      category: "stress",
      platform: "shared",
      status: "failed",
      reason: "Latency exceeded",
    },
    {
      id: "spike",
      name: "Spike test",
      category: "spike",
      platform: "shared",
      status: "blocked",
      reason: "Budget exhausted",
    },
    { id: "soak", name: "Soak test", category: "soak", platform: "shared", status: "cancelled" },
  ],
};
function mount(path = "/loadtesting?session=job-one", data: unknown = report) {
  const fetch = vi
    .fn()
    .mockImplementation(async () => new Response(JSON.stringify(data), { status: 200 }));
  vi.stubGlobal("fetch", fetch);
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[path]}>
        <LoadTestingPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetch;
}
it("uses the exact job and displays failures, gaps, metrics and rerun", async () => {
  const fetch = mount();
  await screen.findByText("Performance thresholds exceeded");
  expect(fetch.mock.calls[0][0]).toBe("/v1/sessions/job-one/loadtesting");
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ action: "ensure" });
  expect(screen.getByText("Latency exceeded")).toBeVisible();
  expect(screen.getByText("Budget exhausted")).toBeVisible();
  expect(screen.getByRole("img", { name: "Load test p95 latency over time" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Run again" }));
  await waitFor(() =>
    expect(JSON.parse(fetch.mock.calls.at(-1)![1].body)).toEqual({
      action: "start",
      max_requests: 100,
    }),
  );
});
it("supports project context and waits without a job", async () => {
  const fetch = mount("/loadtesting?project=Project+A");
  await waitFor(() => expect(fetch.mock.calls[0][0]).toBe("/v1/sessions/project-job/loadtesting"));
  cleanup();
  const none = mount("/loadtesting");
  expect(screen.getByRole("status")).toHaveTextContent("Open Load Testing from a job");
  expect(none).not.toHaveBeenCalled();
});
it("supports cancellation and runtime errors", async () => {
  const fetch = mount(undefined, { ...report, state: "running" });
  fireEvent.click(await screen.findByRole("button", { name: "Stop run" }));
  await waitFor(() =>
    expect(JSON.parse(fetch.mock.calls.at(-1)![1].body)).toEqual({ action: "cancel" }),
  );
  cleanup();
  mount(undefined, { ...report, state: "error", error: "Runtime unavailable" });
  expect(await screen.findByRole("alert")).toHaveTextContent("Runtime unavailable");
});
it("downloads report data", async () => {
  const create = vi.fn().mockReturnValue("blob:report"),
    click = vi.fn();
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: create, revokeObjectURL: vi.fn() }));
  const original = document.createElement.bind(document);
  vi.spyOn(document, "createElement").mockImplementation((name, options) => {
    const element = original(name, options);
    if (name === "a") element.click = click;
    return element;
  });
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Download JSON" }));
  expect(click).toHaveBeenCalledOnce();
  expect(create.mock.calls[0][0]).toBeInstanceOf(Blob);
});

it("sends the selected 100-million request limit only when rerunning", async () => {
  const fetch = mount();
  await screen.findByText("Performance thresholds exceeded");
  const input = screen.getByRole("spinbutton", { name: "Total requests" });
  expect(input).toHaveValue(100);
  fireEvent.change(input, { target: { value: "100000000" } });
  fireEvent.click(screen.getByRole("button", { name: "Run again" }));
  await waitFor(() =>
    expect(JSON.parse(fetch.mock.calls.at(-1)![1].body)).toEqual({
      action: "start",
      max_requests: 100000000,
    }),
  );
});

it.each(["", "0", "-1", "1.5", "100000001"])("rejects invalid request count %s", async (value) => {
  const fetch = mount();
  await screen.findByText("Performance thresholds exceeded");
  fireEvent.change(screen.getByRole("spinbutton", { name: "Total requests" }), {
    target: { value },
  });
  expect(screen.getByRole("button", { name: "Run again" })).toBeDisabled();
  expect(screen.getByRole("alert")).toHaveTextContent("whole number");
  expect(fetch).toHaveBeenCalledTimes(1);
});

it("shows actual request progress against the count-driven total", async () => {
  const counted = {
    ...report,
    checks: report.checks.map((check) => ({
      ...check,
      config: {
        durations: { load: 8, stress: 12, spike: 10, soak: 30 },
        max_requests: 17,
        requests_per_second: 20,
        max_p95_ms: 1000,
        max_error_percent: 1,
        request_mode: "count",
      },
      target_requests: 5,
    })),
  };
  mount(undefined, counted);
  const progress = await screen.findByRole("progressbar", { name: "Request progress" });
  expect(progress).toHaveAttribute("max", "17");
  expect(progress).toHaveAttribute("value", "12");
  expect(screen.getByText("of 17 requested")).toBeVisible();
  expect(screen.getAllByText(/5 requests allocated/).length).toBe(4);
});

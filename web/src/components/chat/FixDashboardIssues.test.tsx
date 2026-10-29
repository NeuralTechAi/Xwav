import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { FixDashboardIssues } from "./FixDashboardIssues";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it.each(["preproduction", "loadtesting", "penetration", "releases"] as const)(
  "sends %s repairs once to the exact job and exposes the live chat",
  async (kind) => {
    const fetch = vi
      .fn()
      .mockImplementation(async () => new Response(JSON.stringify({ queued: true })));
    vi.stubGlobal("fetch", fetch);
    render(
      <MemoryRouter>
        <FixDashboardIssues sessionId="job-one" kind={kind} runId="run-one" />
      </MemoryRouter>,
    );
    const button = screen.getByRole("button", { name: "Fix issues" });
    fireEvent.click(button);
    fireEvent.click(button);
    await waitFor(() => expect(screen.getByText("View repair in job")).toBeVisible());
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toBe("/v1/sessions/job-one/events");
    const request = JSON.parse(fetch.mock.calls[0][1].body);
    expect(request.data.content[0].text).toContain("run-one");
    expect(request.data.content[0].text).toContain("Do not weaken checks or publish");
    expect(screen.getByRole("link")).toHaveAttribute("href", "/c/job-one");
  },
);

it("keeps the send identity on retry and shows denied requests", async () => {
  const fetch = vi
    .fn()
    .mockImplementationOnce(async () => new Response(JSON.stringify({ denied: true })))
    .mockImplementation(async () => new Response(JSON.stringify({ queued: true })));
  vi.stubGlobal("fetch", fetch);
  render(
    <MemoryRouter>
      <FixDashboardIssues sessionId="job" kind="preproduction" />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Fix issues" }));
  await waitFor(() => expect(screen.getByRole("alert")).toBeVisible());
  fireEvent.click(screen.getByRole("button", { name: "Fix issues" }));
  await waitFor(() => expect(screen.getByText("View repair in job")).toBeVisible());
  expect(JSON.parse(fetch.mock.calls[0][1].body).data.stable_id).toBe(
    JSON.parse(fetch.mock.calls[1][1].body).data.stable_id,
  );
});

it("cannot dispatch without a job", () => {
  render(
    <MemoryRouter>
      <FixDashboardIssues sessionId={null} kind="preproduction" />
    </MemoryRouter>,
  );
  expect(screen.getByRole("button")).toBeDisabled();
});

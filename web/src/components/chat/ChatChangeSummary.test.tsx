import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ChatChangeSummary } from "./ChatChangeSummary";

const fetch = vi.hoisted(() => vi.fn());
vi.mock("@/lib/identity", () => ({ authenticatedFetch: fetch }));
beforeEach(() => {
  fetch.mockReset();
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      private callback: (entries: { isIntersecting: boolean }[]) => void;
      constructor(callback: (entries: { isIntersecting: boolean }[]) => void) {
        this.callback = callback;
      }
      observe() {
        this.callback([{ isIntersecting: true }]);
      }
      disconnect() {}
    },
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
function mount(running = false, itemId = "answer") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ChatChangeSummary sessionId="job" itemId={itemId} running={running} />
    </QueryClientProvider>,
  );
}
it("shows a summary and fetches only the clicked file's diff", async () => {
  fetch
    .mockResolvedValueOnce(
      Response.json({
        count: 2,
        scope: "next_request",
        files: [
          { path: "src/app.ts", status: "modified", additions: 2, deletions: 1 },
          { path: "image.png", status: "added", additions: null, deletions: null },
        ],
      }),
    )
    .mockResolvedValueOnce(
      Response.json({
        count: 2,
        files: [
          {
            path: "src/app.ts",
            diff: "--- a/src/app.ts\n+++ b/src/app.ts\n-old\n+new",
            additions: 1,
            deletions: 1,
          },
        ],
      }),
    );
  mount();
  expect(await screen.findByText("2 files changed")).toBeVisible();
  expect(screen.getByText(/From this request to the next request/)).toBeVisible();
  expect(fetch).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByTitle("View changes to src/app.ts"));
  expect(await screen.findByLabelText("Code changes")).toHaveTextContent("+new");
  expect(fetch.mock.calls[1][0]).toContain("path=src%2Fapp.ts");
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
it("waits for an idle job, then loads the summary", async () => {
  fetch.mockResolvedValue(Response.json({ count: 0, scope: "current_workspace", files: [] }));
  const client = new QueryClient();
  const view = render(
    <QueryClientProvider client={client}>
      <ChatChangeSummary sessionId="job" itemId="answer" running />
    </QueryClientProvider>,
  );
  expect(fetch).not.toHaveBeenCalled();
  expect(screen.getByText(/when the job stops/)).toBeVisible();
  view.rerender(
    <QueryClientProvider client={client}>
      <ChatChangeSummary sessionId="job" itemId="answer" running={false} />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("No file changes.")).toBeVisible();
});
it("shows missing checkpoint feedback and supports retry", async () => {
  fetch
    .mockResolvedValueOnce(
      Response.json({ detail: "No file checkpoint was saved for this request" }, { status: 409 }),
    )
    .mockResolvedValueOnce(Response.json({ count: 0, scope: "current_workspace", files: [] }));
  mount();
  expect(await screen.findByText(/No file checkpoint/)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Refresh changes" }));
  expect(await screen.findByText("No file changes.")).toBeVisible();
});
it("discards an old job's late response after navigation", async () => {
  let resolve!: (response: Response) => void;
  fetch
    .mockImplementationOnce(
      () =>
        new Promise<Response>((done) => {
          resolve = done;
        }),
    )
    .mockResolvedValueOnce(Response.json({ count: 0, scope: "current_workspace", files: [] }));
  const client = new QueryClient();
  const view = render(
    <QueryClientProvider client={client}>
      <ChatChangeSummary sessionId="old" itemId="answer" running={false} />
    </QueryClientProvider>,
  );
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  view.rerender(
    <QueryClientProvider client={client}>
      <ChatChangeSummary sessionId="new" itemId="answer" running={false} />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("No file changes.")).toBeVisible();
  resolve(Response.json({ count: 99, scope: "current_workspace", files: [] }));
  await waitFor(() => expect(screen.queryByText("99 files changed")).not.toBeInTheDocument());
});

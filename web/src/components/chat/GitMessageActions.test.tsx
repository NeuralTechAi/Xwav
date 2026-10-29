import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { GitMessageActions } from "./GitMessageActions";

const mocks = vi.hoisted(() => ({
  fetch: vi.fn(),
  live: { status: "idle", sessionStatus: "idle" },
}));
vi.mock("@/lib/identity", () => ({ authenticatedFetch: mocks.fetch }));
vi.mock("@/hooks/useConversationEntryState", () => ({
  useConversationEntryState: () => mocks.live,
}));
beforeEach(() => {
  mocks.fetch.mockReset();
  mocks.live.status = "idle";
  mocks.live.sessionStatus = "idle";
});
afterEach(cleanup);
const status = (staged = false) => ({
  state: "ready",
  branch: "feature",
  repository: "/job",
  files: [{ path: "app.ts", staged, unstaged: !staged }],
  count: 1,
  staged_count: staged ? 1 : 0,
  unstaged_count: staged ? 0 : 1,
  token: "reviewed-index",
});
it("reviews and stages only on confirmation", async () => {
  mocks.fetch
    .mockResolvedValueOnce(Response.json(status()))
    .mockResolvedValueOnce(Response.json({ ...status(true), state: "staged" }));
  render(<GitMessageActions sessionId="job" />);
  fireEvent.click(screen.getByRole("button", { name: "Stage changes" }));
  expect(await screen.findByText("app.ts")).toBeVisible();
  expect(JSON.parse(mocks.fetch.mock.calls[0][1].body)).toEqual({ action: "status" });
  fireEvent.click(screen.getByRole("button", { name: "Stage all changes" }));
  expect(
    await screen.findByText("Project changes staged. Click Commit to create a commit."),
  ).toBeVisible();
  expect(JSON.parse(mocks.fetch.mock.calls[1][1].body)).toEqual({ action: "stage" });
});
it("requires a message and commits only the reviewed index", async () => {
  mocks.fetch
    .mockResolvedValueOnce(Response.json(status(true)))
    .mockResolvedValueOnce(
      Response.json({ ...status(), state: "committed", commit: "abc123456789abcdef" }),
    );
  render(<GitMessageActions sessionId="job" />);
  fireEvent.click(screen.getByRole("button", { name: "Commit changes" }));
  const submit = await screen.findByRole("button", { name: "Create commit" });
  expect(submit).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Commit message"), { target: { value: "Fix app" } });
  fireEvent.click(submit);
  expect(await screen.findByText(/Commit created: abc123456789/)).toBeVisible();
  expect(JSON.parse(mocks.fetch.mock.calls[1][1].body)).toEqual({
    action: "commit",
    message: "Fix app",
    token: "reviewed-index",
  });
  expect(screen.queryByRole("button", { name: "Create commit" })).toBeNull();
});
it("cancel only reads status", async () => {
  mocks.fetch.mockResolvedValue(Response.json(status()));
  render(<GitMessageActions sessionId="job" />);
  fireEvent.click(screen.getByRole("button", { name: "Stage changes" }));
  await screen.findByText("app.ts");
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(mocks.fetch).toHaveBeenCalledTimes(1);
});
it("disables actions while an agent runs", () => {
  mocks.live.sessionStatus = "running";
  render(<GitMessageActions sessionId="job" />);
  expect(screen.getByRole("button", { name: "Stage changes" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Commit changes" })).toBeDisabled();
  expect(mocks.fetch).not.toHaveBeenCalled();
});
it("shows errors and requires a fresh review", async () => {
  mocks.fetch
    .mockResolvedValueOnce(Response.json(status(true)))
    .mockRejectedValueOnce(new Error("Staged files changed"));
  render(<GitMessageActions sessionId="job" />);
  fireEvent.click(screen.getByRole("button", { name: "Commit changes" }));
  await screen.findByLabelText("Commit message");
  fireEvent.change(screen.getByLabelText("Commit message"), { target: { value: "Fix" } });
  fireEvent.click(screen.getByRole("button", { name: "Create commit" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Staged files changed");
  expect(screen.getByRole("button", { name: "Create commit" })).toBeDisabled();
});
it("ignores responses from previous jobs", async () => {
  let resolve!: (response: Response) => void;
  mocks.fetch.mockReturnValue(
    new Promise<Response>((done) => {
      resolve = done;
    }),
  );
  const view = render(<GitMessageActions sessionId="first" />);
  fireEvent.click(screen.getByRole("button", { name: "Stage changes" }));
  view.rerender(<GitMessageActions sessionId="second" />);
  resolve(Response.json(status()));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
});

it("initializes a new project only after an explicit click", async () => {
  mocks.fetch
    .mockResolvedValueOnce(
      Response.json({ state: "not_git", files: [], count: 0, staged_count: 0, unstaged_count: 0 }),
    )
    .mockResolvedValueOnce(Response.json(status()));
  render(<GitMessageActions sessionId="job" />);
  fireEvent.click(screen.getByRole("button", { name: "Stage changes" }));
  const initialize = await screen.findByRole("button", { name: "Initialize Git repository" });
  expect(mocks.fetch).toHaveBeenCalledTimes(1);
  fireEvent.click(initialize);
  expect(await screen.findByText("app.ts")).toBeVisible();
  expect(JSON.parse(mocks.fetch.mock.calls[1][1].body)).toEqual({ action: "init" });
});

it("collects missing Git identity without changing global config", async () => {
  mocks.fetch
    .mockResolvedValueOnce(Response.json({ ...status(true), author_required: true }))
    .mockResolvedValueOnce(Response.json({ ...status(), state: "committed", commit: "abc" }));
  render(<GitMessageActions sessionId="job" />);
  fireEvent.click(screen.getByRole("button", { name: "Commit changes" }));
  await screen.findByLabelText("Author name");
  fireEvent.change(screen.getByLabelText("Commit message"), { target: { value: "Initial" } });
  expect(screen.getByRole("button", { name: "Create commit" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Author name"), { target: { value: "Project Author" } });
  fireEvent.change(screen.getByLabelText("Author email"), {
    target: { value: "author@example.test" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Create commit" }));
  await screen.findByText(/Commit created:/);
  expect(JSON.parse(mocks.fetch.mock.calls[1][1].body)).toMatchObject({
    author_name: "Project Author",
    author_email: "author@example.test",
  });
});

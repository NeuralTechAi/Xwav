import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { RevertMessageAction } from "./RevertMessageAction";

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
const ready = () =>
  Response.json({
    state: "ready",
    count: 1,
    token: "reviewed-version",
    changes: [{ path: "app.ts", action: "restore" }],
  });
describe("Chat file revert", () => {
  it("reviews without writing, requires confirmation and offers backup undo", async () => {
    mocks.fetch
      .mockResolvedValueOnce(ready())
      .mockResolvedValueOnce(
        Response.json({ state: "restored", count: 1, backup_id: "undo_backup" }),
      )
      .mockResolvedValueOnce(ready());
    render(<RevertMessageAction sessionId="job-one" itemId="message-one" />);
    fireEvent.click(screen.getByRole("button", { name: "Revert changes" }));
    expect(await screen.findByText("Restore · app.ts")).toBeVisible();
    expect(mocks.fetch).toHaveBeenCalledTimes(1);
    expect(JSON.parse(mocks.fetch.mock.calls[0][1].body)).toEqual({
      action: "plan",
      item_id: "message-one",
    });
    fireEvent.click(screen.getByRole("button", { name: "Restore files" }));
    expect(
      await screen.findByText("Project files restored. Your chat history is unchanged."),
    ).toBeVisible();
    expect(JSON.parse(mocks.fetch.mock.calls[1][1].body)).toEqual({
      action: "apply",
      item_id: "message-one",
      token: "reviewed-version",
    });
    fireEvent.click(screen.getByRole("button", { name: "Undo revert" }));
    expect(await screen.findByText("Restore · app.ts")).toBeVisible();
    expect(JSON.parse(mocks.fetch.mock.calls[2][1].body)).toEqual({
      action: "plan",
      backup_id: "undo_backup",
    });
  });
  it("cancel never restores files", async () => {
    mocks.fetch.mockResolvedValue(ready());
    render(<RevertMessageAction sessionId="job" itemId="message" />);
    fireEvent.click(screen.getByRole("button", { name: "Revert changes" }));
    await screen.findByRole("button", { name: "Restore files" });
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(mocks.fetch).toHaveBeenCalledTimes(1);
  });
  it("disables pending and running jobs", () => {
    mocks.live.status = "streaming";
    render(<RevertMessageAction sessionId="job" itemId="message" />);
    expect(screen.getByRole("button", { name: "Revert changes" })).toBeDisabled();
    expect(mocks.fetch).not.toHaveBeenCalled();
  });
  it("shows checkpoint errors without claiming success", async () => {
    mocks.fetch.mockRejectedValue(new Error("No checkpoint before this message"));
    render(<RevertMessageAction sessionId="job" itemId="message" />);
    fireEvent.click(screen.getByRole("button", { name: "Revert changes" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No checkpoint before this message");
    expect(screen.queryByRole("button", { name: "Restore files" })).toBeNull();
  });
  it("discards a review when the conversation changes", async () => {
    let resolve!: (response: Response) => void;
    mocks.fetch.mockReturnValue(
      new Promise<Response>((done) => {
        resolve = done;
      }),
    );
    const { rerender } = render(<RevertMessageAction sessionId="first" itemId="message" />);
    fireEvent.click(screen.getByRole("button", { name: "Revert changes" }));
    rerender(<RevertMessageAction sessionId="second" itemId="message" />);
    resolve(ready());
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.queryByRole("button", { name: "Restore files" })).toBeNull();
  });
});

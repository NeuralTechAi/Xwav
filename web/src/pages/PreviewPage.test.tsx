import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type * as SessionsApi from "@/lib/sessionsApi";
import { PreviewPage } from "./PreviewPage";

const mocks = vi.hoisted(() => ({
  status: {
    state: "ready",
    message: "Live project preview",
    port: 41881,
    version: "one",
  } as Record<string, unknown>,
  usePreview: vi.fn(),
  postEvent: vi.fn(),
}));
vi.mock("@/lib/sessionsApi", async (importOriginal) => ({
  ...(await importOriginal<typeof SessionsApi>()),
  postEvent: mocks.postEvent,
}));
vi.mock("@/hooks/useProjectPreview", () => ({
  useProjectPreview: (id: string | null) => {
    mocks.usePreview(id);
    return { data: mocks.status, isError: false };
  },
}));
vi.mock("@/hooks/useConversations", () => ({
  useProjectSessions: () => ({ data: { pages: [{ data: [{ id: "project-job" }] }] } }),
}));
beforeEach(() => {
  mocks.status = { state: "ready", message: "Live project preview", port: 41881, version: "one" };
  mocks.usePreview.mockClear();
  mocks.postEvent.mockReset().mockResolvedValue({ queued: true, itemId: "accepted" });
  vi.stubGlobal(
    "ResizeObserver",
    class {
      callback: ResizeObserverCallback;
      constructor(callback: ResizeObserverCallback) {
        this.callback = callback;
      }
      observe() {
        this.callback(
          [{ contentRect: { width: 600 } } as ResizeObserverEntry],
          this as unknown as ResizeObserver,
        );
      }
      disconnect() {}
    },
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
function renderPreview(path = "/preview?session=job-one") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <PreviewPage />
    </MemoryRouter>,
  );
}

describe("Automatic project preview", () => {
  it("connects to the exact job without asking for a URL", () => {
    renderPreview();
    expect(mocks.usePreview).toHaveBeenCalledWith("job-one");
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(document.querySelectorAll("iframe")).toHaveLength(3);
    const url = new URL(screen.getByTitle("Web app preview").getAttribute("src")!);
    expect(url.origin + url.pathname).toBe("http://127.0.0.1:41881/");
    expect(url.searchParams.get("__xwav_preview_revision")).toBe("job-one:one:0");
    expect(screen.getByTitle("Android app preview")).toHaveAttribute("width", "412");
    expect(screen.getByTitle("iOS app preview")).toHaveAttribute("width", "393");
  });
  it("loads query-intolerant app servers and remounts every frame on source changes", () => {
    mocks.status = { state: "ready", port: 41881, version: "one", revision_query: false };
    const view = renderPreview();
    const frames = Array.from(document.querySelectorAll("iframe"));
    for (const frame of frames) expect(frame.src).toBe("http://127.0.0.1:41881/");
    mocks.status = { state: "ready", port: 41881, version: "two", revision_query: false };
    view.rerender(
      <MemoryRouter initialEntries={["/preview?session=job-one"]}>
        <PreviewPage />
      </MemoryRouter>,
    );
    for (const frame of frames) expect(frame.isConnected).toBe(false);
    expect(document.querySelectorAll("iframe")).toHaveLength(3);
  });
  it("orders mobile panels above Web and reloads only the web app", () => {
    renderPreview();
    expect(screen.getAllByRole("region").map((node) => node.getAttribute("aria-label"))).toEqual([
      "Android preview panel",
      "iOS preview panel",
      "Web preview panel",
    ]);
    const web = screen.getByTitle("Web app preview");
    const android = screen.getByTitle("Android app preview");
    fireEvent.click(screen.getByRole("button", { name: "Reload Web app" }));
    expect(screen.getByTitle("Web app preview")).not.toBe(web);
    expect(screen.getByTitle("Android app preview")).toBe(android);
    fireEvent.click(screen.getByRole("button", { name: "Rotate Android" }));
    expect(android).toHaveAttribute("width", "915");
    expect(android).toHaveAttribute("height", "412");
  });
  it("uses the selected project's latest job when opened before a new job starts", () => {
    renderPreview("/preview?project=Alpha");
    expect(mocks.usePreview).toHaveBeenCalledWith("project-job");
  });
  it("waits for a runnable app instead of showing another project's app", () => {
    mocks.status = { state: "waiting", message: "Waiting for this job’s app" };
    renderPreview();
    expect(document.querySelectorAll("iframe")).toHaveLength(0);
    expect(screen.getByTestId("preview-device-android")).toHaveClass("preview-device-android");
    expect(screen.getByTestId("preview-device-ios")).toHaveClass("preview-device-ios");
    expect(screen.getByRole("img", { name: "Android preview standby screen" })).toBeVisible();
    expect(screen.getByRole("img", { name: "iOS preview standby screen" })).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("Waiting for this job’s app");
  });
  it("minimizes without losing state, maximizes and closes to release resources", () => {
    renderPreview();
    const android = screen.getByTitle("Android app preview");
    fireEvent.click(screen.getByRole("button", { name: "Minimize Android" }));
    expect(android).not.toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Restore Android" }));
    expect(screen.getByTitle("Android app preview")).toBe(android);
    fireEvent.click(screen.getByRole("button", { name: "Maximize Android" }));
    expect(screen.getByTitle("Web app preview")).not.toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Unmaximize Android" }));
    expect(screen.getByTitle("Web app preview")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Close Android" }));
    expect(screen.queryByTitle("Android app preview")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Reopen Android preview" }));
    expect(screen.getByTitle("Android app preview")).toBeInTheDocument();
  });
  it("updates all frames when the runtime reports a source change", () => {
    const { rerender } = renderPreview();
    const frame = screen.getByTitle("Web app preview");
    const previousUrl = frame.getAttribute("src");
    mocks.status = { ...mocks.status, version: "changed-source" };
    rerender(
      <MemoryRouter>
        <PreviewPage />
      </MemoryRouter>,
    );
    expect(screen.getByTitle("Web app preview")).not.toBe(frame);
    for (const name of ["Web", "Android", "iOS"]) {
      const nextUrl = screen.getByTitle(`${name} app preview`).getAttribute("src");
      expect(nextUrl).not.toBe(previousUrl);
      expect(new URL(nextUrl!).searchParams.get("__xwav_preview_revision")).toContain(
        "changed-source",
      );
    }
  });
});

describe("Preview change requests", () => {
  function select(device: string) {
    fireEvent.click(screen.getByRole("button", { name: `Select area in ${device}` }));
    fireEvent.keyDown(screen.getByRole("button", { name: `Select area in ${device} preview` }), {
      key: "Enter",
    });
  }
  it.each(["Web", "Android", "iOS"])(
    "sends the selected %s region to the exact job",
    async (device) => {
      renderPreview();
      select(device);
      const input = screen.getByRole("textbox", { name: "What should change in this area?" });
      expect(input).toHaveFocus();
      expect(screen.getByTestId(`preview-selection-${device.toLowerCase()}`)).toBeVisible();
      fireEvent.change(input, { target: { value: "Make the selected button green" } });
      fireEvent.click(screen.getByRole("button", { name: "Request change" }));
      await waitFor(() => expect(mocks.postEvent).toHaveBeenCalledOnce());
      const [id, event] = mocks.postEvent.mock.calls[0];
      expect(id).toBe("job-one");
      expect(event.data.stable_id).toMatch(/^[a-f0-9]{32}$/);
      expect(event.data.content[0].text).toContain(`Device: ${device} responsive web preview`);
      expect(event.data.content[0].text).toContain("Selected visible region:");
      expect(event.data.content[0].text).toContain(
        "Apply the requested change consistently across Web, Android, and iOS previews.",
      );
      expect(event.data.content[0].text).toContain("not the scope of the change");
      expect(event.data.content[0].text).toContain("Check the result at all three viewport sizes");
      expect(event.data.content[0].text).toContain("Make the selected button green");
      await waitFor(() => expect(screen.getByText(/Request sent to the job/)).toBeVisible());
    },
  );
  it("lets users refine coordinates without losing numeric-field focus and sends the exact result", async () => {
    renderPreview();
    select("Web");
    const x = screen.getByRole("spinbutton", { name: "Web selection x" });
    x.focus();
    fireEvent.change(x, { target: { value: "123" } });
    expect(x).toHaveFocus();
    fireEvent.change(screen.getByRole("spinbutton", { name: "Web selection y" }), {
      target: { value: "89" },
    });
    fireEvent.change(screen.getByRole("spinbutton", { name: "Web selection width" }), {
      target: { value: "7" },
    });
    fireEvent.change(screen.getByRole("spinbutton", { name: "Web selection height" }), {
      target: { value: "5" },
    });
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Change this precise area" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Request change" }));
    await waitFor(() => expect(mocks.postEvent).toHaveBeenCalledOnce());
    expect(mocks.postEvent.mock.calls[0][1].data.content[0].text).toContain(
      "x=123, y=89, width=7, height=5",
    );
  });
  it("focuses the selection surface and editor without moving the page", () => {
    const focus = vi.spyOn(HTMLElement.prototype, "focus");
    renderPreview();
    fireEvent.click(screen.getByRole("button", { name: "Select area in Web" }));
    const surface = screen.getByRole("button", { name: "Select area in Web preview" });
    expect(surface).toHaveFocus();
    expect(focus).toHaveBeenLastCalledWith({ preventScroll: true });
    fireEvent.keyDown(surface, { key: "Enter" });
    expect(screen.getByRole("textbox")).toHaveFocus();
    expect(focus).toHaveBeenLastCalledWith({ preventScroll: true });
    focus.mockRestore();
  });
  it("keeps failed drafts and retries the same send id, without double submission", async () => {
    mocks.postEvent.mockRejectedValueOnce(new Error("Runtime disconnected"));
    renderPreview();
    select("Android");
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "Adjust the spacing" } });
    fireEvent.click(screen.getByRole("button", { name: "Request change" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Runtime disconnected"),
    );
    expect(input).toHaveValue("Adjust the spacing");
    const firstId = mocks.postEvent.mock.calls[0][1].data.stable_id;
    fireEvent.click(screen.getByRole("button", { name: "Request change" }));
    await waitFor(() => expect(screen.getByText(/Request sent/)).toBeVisible());
    expect(mocks.postEvent.mock.calls[1][1].data.stable_id).toBe(firstId);
  });
  it("retains a policy denied request and shows the failure", async () => {
    mocks.postEvent.mockResolvedValue({ denied: true, queued: false });
    renderPreview();
    select("iOS");
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Change this heading" } });
    fireEvent.click(screen.getByRole("button", { name: "Request change" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("policy"));
    expect(screen.getByRole("textbox")).toHaveValue("Change this heading");
  });
  it.each(["Web", "Android", "iOS"])(
    "keeps the %s selection and editor stable during live source updates",
    (device) => {
      const view = renderPreview();
      const frame = screen.getByTitle(`${device} app preview`);
      const previousUrl = frame.getAttribute("src");
      select(device);
      fireEvent.change(screen.getByRole("textbox"), { target: { value: "Keep this draft" } });
      mocks.status = { ...mocks.status, version: "new-source" };
      view.rerender(
        <MemoryRouter>
          <PreviewPage />
        </MemoryRouter>,
      );
      expect(screen.getByTestId(`preview-selection-${device.toLowerCase()}`)).toBeVisible();
      expect(screen.getByTitle(`${device} app preview`)).toBe(frame);
      expect(frame).toHaveAttribute("src", previousUrl);
      expect(screen.getByRole("textbox")).toHaveValue("Keep this draft");
      expect(mocks.postEvent).not.toHaveBeenCalled();
      fireEvent.click(screen.getByRole("button", { name: `Clear ${device} selection` }));
      expect(
        new URL(screen.getByTitle(`${device} app preview`).getAttribute("src")!).searchParams.get(
          "__xwav_preview_revision",
        ),
      ).toContain("new-source");
    },
  );
  it("keeps a pending request locked and acknowledges it when source updates arrive before the response", async () => {
    let finish!: (value: { queued: boolean }) => void;
    mocks.postEvent.mockReturnValue(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    const view = renderPreview();
    select("Web");
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Update the heading" } });
    fireEvent.click(screen.getByRole("button", { name: "Request change" }));
    mocks.status = { ...mocks.status, version: "updated-while-sending" };
    view.rerender(
      <MemoryRouter>
        <PreviewPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole("button", { name: "Sending…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Select area in Web" })).toBeDisabled();
    finish({ queued: true });
    await waitFor(() => expect(screen.getByText(/Request sent to the job/)).toBeVisible());
    expect(mocks.postEvent).toHaveBeenCalledOnce();
    expect(
      new URL(screen.getByTitle("Web app preview").getAttribute("src")!).searchParams.get(
        "__xwav_preview_revision",
      ),
    ).toContain("updated-while-sending");
  });
  it("does not discard a selection when the iframe finishes loading late", () => {
    renderPreview();
    select("Web");
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Keep this selection" } });
    fireEvent.load(screen.getByTitle("Web app preview"));
    expect(screen.getByTestId("preview-selection-web")).toBeVisible();
    expect(screen.getByRole("textbox")).toHaveValue("Keep this selection");
  });
  it("keeps the pending send and its acknowledgement through a temporary app restart", async () => {
    let finish!: (value: { queued: boolean }) => void;
    mocks.postEvent.mockReturnValue(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    const view = renderPreview();
    select("Android");
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Change during restart" } });
    fireEvent.click(screen.getByRole("button", { name: "Request change" }));
    mocks.status = { state: "starting", port: 41881 };
    view.rerender(
      <MemoryRouter>
        <PreviewPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("Sending your change request to the job…")).toBeVisible();
    finish({ queued: true });
    await waitFor(() => expect(screen.getByText(/Request sent to the job/)).toBeVisible());
    mocks.status = { state: "ready", port: 41881, version: "restarted" };
    view.rerender(
      <MemoryRouter>
        <PreviewPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Request sent to the job/)).toBeVisible();
    expect(mocks.postEvent).toHaveBeenCalledOnce();
  });
  it("preserves a selected draft across minimize/restore and locks picking during a send", async () => {
    let finish!: (value: { queued: boolean }) => void;
    mocks.postEvent.mockReturnValue(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    renderPreview();
    select("Android");
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Resize this card" } });
    fireEvent.click(screen.getByRole("button", { name: "Minimize Android" }));
    expect(screen.getByLabelText("What should change in this area?")).not.toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Restore Android" }));
    expect(screen.getByRole("textbox")).toHaveValue("Resize this card");
    fireEvent.click(screen.getByRole("button", { name: "Request change" }));
    expect(screen.getByRole("button", { name: "Select area in Android" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Sending…" })).toBeDisabled();
    expect(mocks.postEvent).toHaveBeenCalledOnce();
    finish({ queued: true });
    await waitFor(() => expect(screen.getByText(/Request sent/)).toBeVisible());
  });
  it("cancels selection and disables picking on standby", () => {
    renderPreview();
    fireEvent.click(screen.getByRole("button", { name: "Select area in Web" }));
    fireEvent.keyDown(screen.getByRole("button", { name: "Select area in Web preview" }), {
      key: "Escape",
    });
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(mocks.postEvent).not.toHaveBeenCalled();
    cleanup();
    mocks.status = { state: "waiting" };
    renderPreview();
    expect(screen.getByRole("button", { name: "Select area in Web" })).toBeDisabled();
  });
});

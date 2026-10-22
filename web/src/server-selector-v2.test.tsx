import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, expect, it, vi } from "vitest";
import { BridgeSetupApp, SetupApp } from "./server-selector-v2";

afterEach(() => {
  cleanup();
  localStorage.removeItem("web-theme");
  document.documentElement.classList.remove("dark", "light");
  vi.restoreAllMocks();
  delete (window as { omnigentSetup?: unknown }).omnigentSetup;
});

/** Install a minimal `omnigentSetup` bridge; `over` replaces its defaults. */
function stubBridge(over: Record<string, unknown>) {
  (window as { omnigentSetup?: unknown }).omnigentSetup = {
    getServerUrl: async () => null,
    getRecentServers: async () => ["https://team.example.com/"],
    getManagedServers: async () => [],
    getCliStatus: async () => ({ installed: true }),
    copyText: async () => {},
    startLocalServer: async () => ({ ok: false }),
    ...over,
  };
}

it("reserves a full-width 48px desktop title-bar band", async () => {
  stubBridge({});
  const { container } = render(<BridgeSetupApp />);
  await screen.findByRole("button", { name: /open xwav/i });
  expect(container.firstElementChild).toHaveStyle({
    position: "fixed",
    top: "0px",
    left: "0px",
    right: "0px",
    height: "48px",
  });
});

it("marks the desktop title-bar band as a window drag region", () => {
  stubBridge({});
  expect(renderToStaticMarkup(<BridgeSetupApp />)).toMatch(
    /^<div style="[^"]*-webkit-app-region:drag[;"]/,
  );
});

it("tags a connect with a request ID, shows only its phases, and cancels it", async () => {
  let progress: (p: { requestId?: string; phase?: string }) => void = () => {};
  let finish: (r: { cancelled?: boolean }) => void = () => {};
  const setServerUrl = vi.fn(
    (_url: string, _opts?: { requestId?: string }) =>
      new Promise<{ cancelled?: boolean }>((resolve) => {
        finish = resolve;
      }),
  );
  const cancelServerConnection = vi.fn().mockResolvedValue(true);
  stubBridge({
    setServerUrl,
    cancelServerConnection,
    onConnectionProgress: (cb: typeof progress) => {
      progress = cb;
      return () => {};
    },
  });
  render(<BridgeSetupApp />);
  const openButton = await screen.findByRole("button", { name: /open xwav/i });
  await waitFor(() => expect(openButton).toBeEnabled());
  fireEvent.click(openButton);
  await waitFor(() => expect(setServerUrl).toHaveBeenCalledTimes(1));
  const requestId = setServerUrl.mock.calls[0][1]?.requestId;
  expect(requestId).toEqual(expect.any(String));

  act(() => progress({ requestId: "someone-else", phase: "authenticating" }));
  expect(screen.queryByText(/finish signing in/i)).not.toBeInTheDocument();
  act(() => progress({ requestId, phase: "authenticating" }));
  expect(screen.getByText(/finish signing in/i)).toBeInTheDocument();

  await act(async () => fireEvent.click(screen.getByRole("button", { name: "Cancel" })));
  expect(cancelServerConnection).toHaveBeenCalledWith(requestId);
  // The shell's late result after a confirmed cancel reads as cancelled: idle, no error.
  await act(async () => finish({}));
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("a cancel from the shell (workspace picker closed) fails the terminal with Retry", async () => {
  stubBridge({
    getManagedServers: async () => ["https://team.example.com/"],
    getRecentServers: async () => [],
    getRunnerOptions: async () => ({ remote: false, bundledCli: true }),
    connectRunner: async () => ({ ok: true }),
    setServerUrl: async () => ({ cancelled: true }),
  });
  render(<BridgeSetupApp />);
  fireEvent.click(await screen.findByRole("button", { name: /join your team/i }));
  fireEvent.click(await screen.findByRole("button", { name: /open xwav/i }));
  expect(await screen.findByText("Connection cancelled.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  expect(screen.queryByText(/server ready/i)).not.toBeInTheDocument();
});

it("shows manual instructions without an installer and detects the CLI after installation", async () => {
  const getCliStatus = vi
    .fn()
    .mockResolvedValueOnce({ installed: false, installSupported: false })
    .mockResolvedValueOnce({ installed: false, installSupported: false })
    .mockResolvedValueOnce({ installed: true, installSupported: false });
  const startLocalServer = vi.fn().mockResolvedValue({ ok: true, url: "http://localhost:6767/" });
  const installCli = vi.fn();
  const setServerUrl = vi.fn().mockResolvedValue({});
  stubBridge({
    getRecentServers: async () => [],
    getCliStatus,
    startLocalServer,
    installCli,
    setServerUrl,
  });
  render(<BridgeSetupApp />);
  fireEvent.click(await screen.findByRole("button", { name: /get started locally/i }));
  fireEvent.click(screen.getByRole("button", { name: "Install Xwav" }));
  expect(screen.getByRole("link", { name: "Installation instructions" })).toHaveAttribute(
    "href",
    "https://github.com/NeuralTechAi/Xwav#run-this-fork-locally",
  );
  expect(screen.queryByRole("button", { name: "Continue anyway" })).not.toBeInTheDocument();
  expect(installCli).not.toHaveBeenCalled();
  expect(startLocalServer).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Check again" }));
  await screen.findByRole("alert");
  expect(startLocalServer).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Check again" }));
  await waitFor(() => expect(setServerUrl).toHaveBeenCalledWith("http://localhost:6767/"));
  expect(installCli).not.toHaveBeenCalled();
  expect(startLocalServer).toHaveBeenCalledOnce();
});

it("keeps remote connections available without a CLI or installer", async () => {
  const setServerUrl = vi.fn().mockResolvedValue({});
  const startLocalServer = vi.fn();
  const installCli = vi.fn();
  stubBridge({
    getCliStatus: async () => ({ installed: false, installSupported: false }),
    setServerUrl,
    startLocalServer,
    installCli,
  });
  render(<BridgeSetupApp />);
  fireEvent.click(await screen.findByRole("button", { name: "Open Xwav" }));
  await waitFor(() => expect(setServerUrl).toHaveBeenCalledOnce());
  expect(startLocalServer).not.toHaveBeenCalled();
  expect(installCli).not.toHaveBeenCalled();
});

it("shows source-install instructions in a browser without the desktop bridge", async () => {
  delete (window as { omnigentSetup?: unknown }).omnigentSetup;
  render(<BridgeSetupApp />);
  fireEvent.click(await screen.findByRole("button", { name: "Get started locally" }));
  fireEvent.click(screen.getByRole("button", { name: "Install Xwav" }));
  expect(screen.getByRole("link", { name: "Installation instructions" })).toHaveAttribute(
    "href",
    "https://github.com/NeuralTechAi/Xwav#run-this-fork-locally",
  );
  expect(screen.getByRole("button", { name: "Check again" })).toBeDisabled();
  expect(screen.queryByText("The desktop shell is unavailable.")).not.toBeInTheDocument();
});

it.each(["light", "dark"] as const)(
  "persists browser onboarding %s mode across reloads",
  async (mode) => {
    const view = render(<SetupApp />);
    fireEvent.pointerDown(await screen.findByRole("button", { name: "Server selector settings" }), {
      button: 0,
    });
    fireEvent.click(
      screen.getByRole("menuitemradio", { name: mode === "dark" ? "Dark" : "Light" }),
    );
    await waitFor(() => expect(document.documentElement).toHaveClass(mode));
    expect(localStorage.getItem("web-theme")).toBe(mode);
    view.unmount();
    document.documentElement.classList.remove(mode);
    render(<SetupApp />);
    await waitFor(() => expect(document.documentElement).toHaveClass(mode));
    fireEvent.pointerDown(await screen.findByRole("button", { name: "Server selector settings" }), {
      button: 0,
    });
    expect(
      screen.getByRole("menuitemradio", { name: mode === "dark" ? "Dark" : "Light" }),
    ).toHaveAttribute("aria-checked", "true");
  },
);

it("follows live OS appearance changes in browser System mode", async () => {
  let onChange: (event: MediaQueryListEvent) => void = () => {};
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  vi.spyOn(window, "matchMedia").mockReturnValue({
    ...media,
    matches: true,
    addListener: (listener) => {
      onChange = listener ?? (() => {});
    },
  });
  render(<SetupApp />);
  await waitFor(() => expect(document.documentElement).toHaveClass("dark"));
  fireEvent.pointerDown(await screen.findByRole("button", { name: "Server selector settings" }), {
    button: 0,
  });
  expect(screen.getByRole("menuitemradio", { name: "System (default)" })).toHaveAttribute(
    "aria-checked",
    "true",
  );
  Object.defineProperty(window.matchMedia("(prefers-color-scheme: dark)"), "matches", {
    value: false,
  });
  act(() => onChange({ matches: false } as MediaQueryListEvent));
  await waitFor(() => expect(document.documentElement).toHaveClass("light"));
});

it("retains desktop appearance controls and native theme ownership", async () => {
  const setColorScheme = vi.fn();
  let onChange: (theme: "light" | "dark") => void = () => {};
  stubBridge({
    setColorScheme,
    getColorScheme: async () => ({ source: "dark", effective: "dark" }),
    onColorScheme: (listener: typeof onChange) => {
      onChange = listener ?? (() => {});
      return () => {};
    },
  });
  render(<SetupApp />);
  fireEvent.pointerDown(await screen.findByRole("button", { name: "Server selector settings" }), {
    button: 0,
  });
  expect(screen.getByRole("menuitemradio", { name: "Dark" })).toHaveAttribute(
    "aria-checked",
    "true",
  );
  fireEvent.click(screen.getByRole("menuitemradio", { name: "Light" }));
  expect(setColorScheme).toHaveBeenCalledWith("light");
  act(() => onChange("light"));
  expect(document.documentElement).not.toHaveClass("dark");
  expect(localStorage.getItem("web-theme")).toBeNull();
});

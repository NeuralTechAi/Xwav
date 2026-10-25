import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ReleasePage } from "./ReleasePage";
import { triggerBrowserDownload } from "@/hooks/useFileContent";

vi.mock("@/hooks/useConversations", () => ({
  useProjectSessions: () => ({ data: { pages: [{ data: [{ id: "project-job" }] }] } }),
}));
vi.mock("@/hooks/useFileContent", () => ({ triggerBrowserDownload: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});
const empty = {
  state: "empty",
  checks: [],
  plans: ["web", "android", "ios", "windows"].map((target) => ({
    target,
    ready: true,
    reason: "",
  })),
};
function mount(
  mode: "deploy" | "download" = "deploy",
  report: unknown = empty,
  path = "/deployments?session=job-one",
) {
  const fetch = vi
    .fn()
    .mockImplementation(
      async () =>
        new Response(JSON.stringify(report), { headers: { "content-type": "application/json" } }),
    );
  vi.stubGlobal("fetch", fetch);
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[path]}>
        <ReleasePage mode={mode} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetch;
}
it("opens without publishing and requires an explicit web provider choice", async () => {
  const fetch = mount();
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(fetch.mock.calls[0][0]).toBe("/v1/sessions/job-one/releases");
  expect(JSON.parse(fetch.mock.calls[0][1].body).action).toBe("status");
  expect(screen.getByRole("button", { name: "Build & deploy" })).toBeDisabled();
  expect(screen.getByRole("option", { name: "Vercel" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "Netlify" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "Cloudflare Pages" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "Railway" })).toBeInTheDocument();
});
it.each(["vercel", "netlify", "cloudflare", "railway", "project"])(
  "passes the user's %s destination to the job",
  async (provider) => {
    const fetch = mount();
    fireEvent.change(screen.getByLabelText("Web deployment destination"), {
      target: { value: provider },
    });
    if (provider === "cloudflare")
      fireEvent.change(screen.getByLabelText("Destination project"), {
        target: { value: "my-site" },
      });
    const button = screen.getByRole("button", { name: "Build & deploy" });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);
    await waitFor(() =>
      expect(
        fetch.mock.calls.some(([, init]) => {
          const body = JSON.parse(init.body);
          return (
            body.action === "start" &&
            body.provider === provider &&
            body.operation === "deploy" &&
            body.target === "web"
          );
        }),
      ).toBe(true),
    );
  },
);
it("offers Windows, Android and iOS downloads and shows missing tooling honestly", async () => {
  mount("download", {
    ...empty,
    plans: [{ target: "windows", ready: false, reason: "Windows or Wine required" }],
  });
  expect(await screen.findByText("Windows or Wine required")).toBeVisible();
  expect(screen.getByRole("button", { name: "Build installer" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Windows" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "Android" })).toBeVisible();
  expect(screen.getByRole("button", { name: "iOS" })).toBeVisible();
});
it("supports cancellation and prevents changing destinations during a build", async () => {
  const fetch = mount("deploy", {
    ...empty,
    state: "running",
    checks: [{ target: "web", operation: "deploy", status: "running", phase: "Publishing" }],
  });
  fireEvent.click(await screen.findByRole("button", { name: "Stop" }));
  await waitFor(() =>
    expect(fetch.mock.calls.some(([, init]) => JSON.parse(init.body).action === "cancel")).toBe(
      true,
    ),
  );
  expect(screen.getByLabelText("Web deployment destination")).toBeDisabled();
});
it("downloads only completed installable artifacts through authenticated requests", async () => {
  const fetch = mount("download", {
    ...empty,
    id: "a".repeat(32),
    state: "complete",
    checks: [{ target: "android", operation: "build", status: "passed" }],
    artifacts: [
      { name: "app.apk", installable: true, bytes: 3, sha256: "abc" },
      { name: "app.aab", installable: false, bytes: 16, sha256: "xyz" },
    ],
  });
  fireEvent.click(screen.getByRole("button", { name: "Android" }));
  const button = await screen.findByRole("button", { name: "Download package" });
  expect(screen.queryByText("app.aab")).toBeNull();
  fetch.mockResolvedValueOnce(
    new Response("APK", { headers: { "content-type": "application/vnd.android.package-archive" } }),
  );
  fireEvent.click(button);
  await waitFor(() =>
    expect(triggerBrowserDownload).toHaveBeenCalledWith(expect.any(Blob), "app.apk"),
  );
  expect(fetch.mock.calls.at(-1)?.[0]).toContain("/releases/" + "a".repeat(32) + "/app.apk");
});
it("does not fetch or deploy before a job exists", () => {
  const fetch = mount("deploy", empty, "/deployments");
  expect(screen.getByRole("status")).toHaveTextContent("saved job");
  expect(fetch).not.toHaveBeenCalled();
});
it("resolves a project's latest job", async () => {
  const fetch = mount("deploy", empty, "/deployments?project=My+project");
  await waitFor(() => expect(fetch.mock.calls[0]?.[0]).toBe("/v1/sessions/project-job/releases"));
});

it("requires Android SDK acceptance before starting automatic setup", async () => {
  const report = {
    ...empty,
    plans: empty.plans.map((plan) => ({
      ...plan,
      android_licenses_required: plan.target === "android",
      setup: "Missing build tools are downloaded automatically and cached when you start.",
    })),
  };
  const fetch = mount("download", report);
  fireEvent.click(screen.getByRole("button", { name: "Android" }));
  const button = screen.getByRole("button", { name: "Build installer" });
  await screen.findByRole("checkbox");
  expect(button).toBeEnabled();
  fireEvent.click(button);
  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByRole("button", { name: "Continue build" })).toBeDisabled();
  expect(fetch.mock.calls.every(([, init]) => JSON.parse(init.body).action === "status")).toBe(
    true,
  );
  fireEvent.click(within(dialog).getByRole("checkbox"));
  await waitFor(() =>
    expect(within(dialog).getByRole("button", { name: "Continue build" })).toBeEnabled(),
  );
  fireEvent.click(within(dialog).getByRole("button", { name: "Continue build" }));
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(([, init]) => {
        const body = JSON.parse(init.body);
        return (
          body.action === "start" &&
          body.target === "android" &&
          body.accept_android_licenses === true
        );
      }),
    ).toBe(true),
  );
});

it("keeps typed destinations stable while checking readiness", async () => {
  const fetch = mount();
  fireEvent.change(screen.getByLabelText("Web deployment destination"), {
    target: { value: "cloudflare" },
  });
  const input = screen.getByLabelText("Destination project");
  fireEvent.change(input, { target: { value: "my-live-site" } });
  expect(input).toHaveValue("my-live-site");
  const button = screen.getByRole("button", { name: "Build & deploy" });
  expect(button).toBeDisabled();
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(([, init]) => {
        const body = JSON.parse(init.body);
        return body.action === "start" && body.site === "my-live-site";
      }),
    ).toBe(true),
  );
});
it("offers web ZIP builds and displays live build output", async () => {
  mount("download", {
    ...empty,
    state: "running",
    checks: [
      { target: "web", operation: "build", status: "running", live_output: "Bundling frontend…" },
    ],
  });
  expect(await screen.findByText("Bundling frontend…")).toBeVisible();
  expect(screen.getByRole("button", { name: "Web" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Working…" })).toBeDisabled();
});
it("rejects truncated packages instead of saving them", async () => {
  const fetch = mount("download", {
    ...empty,
    id: "a".repeat(32),
    state: "complete",
    checks: [{ target: "windows", operation: "build", status: "passed" }],
    artifacts: [{ name: "app.exe", installable: true, bytes: 100, sha256: "abc" }],
  });
  const button = await screen.findByRole("button", { name: "Download package" });
  fetch.mockResolvedValueOnce(
    new Response("short", { headers: { "content-type": "application/octet-stream" } }),
  );
  fireEvent.click(button);
  expect(await screen.findByRole("alert")).toHaveTextContent("incomplete");
  expect(triggerBrowserDownload).not.toHaveBeenCalled();
});

it("builds a downloadable web package", async () => {
  const fetch = mount("download");
  fireEvent.click(screen.getByRole("button", { name: "Web" }));
  const button = screen.getByRole("button", { name: "Build web package" });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(([, init]) => {
        const body = JSON.parse(init.body);
        return body.action === "start" && body.target === "web" && body.operation === "build";
      }),
    ).toBe(true),
  );
});
it("prepares cloud workflows only on request and explains environment signing setup", async () => {
  const fetch = mount("download");
  fireEvent.change(screen.getByLabelText("Build computer"), { target: { value: "github" } });
  expect(await screen.findByRole("region", { name: "Cloud setup" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Prepare cloud workflow" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("GitHub repository"), { target: { value: "owner/app" } });
  expect(screen.getByRole("link", { name: /Open GitHub environments/ })).toHaveAttribute(
    "href",
    "https://github.com/owner/app/settings/environments",
  );
  expect(fetch.mock.calls.some(([, init]) => JSON.parse(init.body).action === "prepare")).toBe(
    false,
  );
  fireEvent.click(screen.getByRole("button", { name: "Prepare cloud workflow" }));
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(([, init]) => {
        const body = JSON.parse(init.body);
        return (
          body.action === "prepare" && body.engine === "github" && body.repository === "owner/app"
        );
      }),
    ).toBe(true),
  );
  expect(screen.getByText(/Add required reviewers to xwav-production/)).toBeVisible();
});
it("defaults cloud publishing to testing and gates production on an explicit choice", async () => {
  const fetch = mount();
  fireEvent.change(screen.getByLabelText("Build computer"), { target: { value: "github" } });
  fireEvent.click(screen.getByRole("button", { name: /^iOS$/ }));
  expect(screen.getByLabelText("Publishing destination")).toHaveValue("testing");
  fireEvent.change(screen.getByLabelText("Publishing destination"), {
    target: { value: "production" },
  });
  const start = screen.getByRole("button", { name: "Build & deploy" });
  await waitFor(() => expect(start).toBeEnabled());
  fireEvent.click(start);
  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByRole("button", { name: "Continue deployment" })).toBeDisabled();
  fireEvent.click(
    within(dialog).getByRole("checkbox", { name: /I confirm production publishing/ }),
  );
  await waitFor(() =>
    expect(within(dialog).getByRole("button", { name: "Continue deployment" })).toBeEnabled(),
  );
  fireEvent.click(within(dialog).getByRole("button", { name: "Continue deployment" }));
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(([, init]) => {
        const body = JSON.parse(init.body);
        return body.action === "start" && body.engine === "github" && body.channel === "production";
      }),
    ).toBe(true),
  );
});
it("shows the specific cloud worker log link and source revision", async () => {
  mount("download", {
    ...empty,
    cloud_run_url: "https://github.com/owner/app/actions/runs/42",
    source_commit: "1234567890abcdef",
  });
  expect(await screen.findByRole("link", { name: /Open cloud build logs/ })).toHaveAttribute(
    "href",
    "https://github.com/owner/app/actions/runs/42",
  );
  expect(screen.getByText("Source revision: 1234567890ab")).toBeVisible();
});

it.each([
  ["deploy", "android", "Android", "Build & deploy"],
  ["deploy", "ios", "iOS", "Build & deploy"],
  ["download", "android", "Android", "Build installer"],
  ["download", "ios", "iOS", "Build installer"],
] as const)(
  "opens actionable setup for blocked %s %s builds",
  async (mode, target, label, action) => {
    const fetch = mount(mode, {
      ...empty,
      plans: empty.plans.map((plan) => ({
        ...plan,
        ready: false,
        reason: "Configure signing and the build computer",
      })),
    });
    fireEvent.click(screen.getByRole("button", { name: label }));
    await screen.findByText("Configure signing and the build computer");
    const button = screen.getByRole("button", { name: action });
    expect(button).toBeEnabled();
    fireEvent.click(button);
    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByRole("heading", {
        name: `Set up ${label} ${mode === "deploy" ? "deployment" : "build"}`,
      }),
    ).toBeVisible();
    expect(within(dialog).getByText("Configure signing and the build computer")).toBeVisible();
    expect(within(dialog).getByRole("button", { name: /Continue/ })).toBeDisabled();
    expect(fetch.mock.calls.some(([, init]) => JSON.parse(init.body).action === "start")).toBe(
      false,
    );
    fireEvent.click(within(dialog).getByRole("button", { name: "Use GitHub Actions" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Build computer")).toHaveValue("github");
    expect(screen.getByRole("region", { name: "Cloud setup" })).toBeVisible();
    expect(fetch.mock.calls.some(([, init]) => JSON.parse(init.body).target === target)).toBe(true);
  },
);
it.each([
  ["deploy", "android", "Android", "Build & deploy"],
  ["deploy", "ios", "iOS", "Build & deploy"],
  ["download", "android", "Android", "Build installer"],
  ["download", "ios", "iOS", "Build installer"],
] as const)("starts ready %s %s builds directly", async (mode, target, label, action) => {
  const fetch = mount(mode);
  fireEvent.click(screen.getByRole("button", { name: label }));
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Ready to start"));
  fireEvent.click(screen.getByRole("button", { name: action }));
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(([, init]) => {
        const body = JSON.parse(init.body);
        return (
          body.action === "start" &&
          body.target === target &&
          body.operation === (mode === "deploy" ? "deploy" : "build")
        );
      }),
    ).toBe(true),
  );
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("keeps the mobile action usable while readiness is pending and waits before starting", async () => {
  const fetch = mount("download");
  await screen.findByText(/Ready to start/);
  let resolveStatus!: (response: Response) => void;
  fetch.mockImplementationOnce(
    () =>
      new Promise<Response>((resolve) => {
        resolveStatus = resolve;
      }),
  );
  fireEvent.click(screen.getByRole("button", { name: "iOS" }));
  const button = screen.getByRole("button", { name: "Build installer" });
  expect(button).toBeEnabled();
  fireEvent.click(button);
  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByRole("status")).toHaveTextContent("Checking");
  expect(within(dialog).getByRole("button", { name: "Continue build" })).toBeDisabled();
  expect(fetch.mock.calls.some(([, init]) => JSON.parse(init.body).action === "start")).toBe(false);
  resolveStatus(
    new Response(JSON.stringify(empty), { headers: { "content-type": "application/json" } }),
  );
  await waitFor(() =>
    expect(within(dialog).getByRole("button", { name: "Continue build" })).toBeEnabled(),
  );
  fireEvent.click(within(dialog).getByRole("button", { name: "Continue build" }));
  await waitFor(() =>
    expect(fetch.mock.calls.some(([, init]) => JSON.parse(init.body).action === "start")).toBe(
      true,
    ),
  );
});
it("allows a failed mobile readiness request to be retried from setup", async () => {
  const fetch = mount("download");
  await screen.findByText(/Ready to start/);
  fetch.mockRejectedValueOnce(new Error("The job is temporarily offline"));
  fireEvent.click(screen.getByRole("button", { name: "iOS" }));
  await screen.findByRole("alert");
  const button = screen.getByRole("button", { name: "Build installer" });
  expect(button).toBeEnabled();
  fireEvent.click(button);
  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByRole("status")).toHaveTextContent("temporarily offline");
  expect(within(dialog).getByRole("button", { name: "Continue build" })).toBeDisabled();
  expect(fetch.mock.calls.some(([, init]) => JSON.parse(init.body).action === "start")).toBe(false);
  fireEvent.click(within(dialog).getByRole("button", { name: "Check again" }));
  await waitFor(() =>
    expect(within(dialog).getByRole("button", { name: "Continue build" })).toBeEnabled(),
  );
});

it("hides previous packages immediately while a new build request starts", async () => {
  const report = {
    ...empty,
    state: "complete",
    id: "a".repeat(32),
    checks: [{ target: "ios", operation: "build", status: "passed" }],
    artifacts: [{ name: "old.ipa", installable: true, bytes: 3, sha256: "abc" }],
  };
  const fetch = mount("download", report);
  fireEvent.click(screen.getByRole("button", { name: "iOS" }));
  await screen.findByRole("button", { name: "Download package" });
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Ready to start"));
  let resolveStart!: (response: Response) => void;
  fetch.mockImplementationOnce(
    () =>
      new Promise<Response>((resolve) => {
        resolveStart = resolve;
      }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Build installer" }));
  expect(screen.queryByRole("button", { name: "Download package" })).not.toBeInTheDocument();
  expect(screen.queryByText("old.ipa")).not.toBeInTheDocument();
  resolveStart(
    new Response(
      JSON.stringify({
        ...empty,
        state: "running",
        checks: [{ target: "ios", operation: "build", status: "running" }],
      }),
      { headers: { "content-type": "application/json" } },
    ),
  );
  await waitFor(() => expect(screen.getByRole("button", { name: "Stop" })).toBeVisible());
});

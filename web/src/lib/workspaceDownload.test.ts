import { beforeEach, expect, it, vi } from "vitest";
import { authenticatedFetch } from "@/lib/identity";
import { triggerBrowserDownload } from "@/hooks/useFileContent";
import { fetchProjectSessionsPage } from "@/hooks/useConversations";
import { downloadJobWorkspace, downloadLatestProjectWorkspace } from "./workspaceDownload";

vi.mock("@/lib/identity", () => ({ authenticatedFetch: vi.fn() }));
vi.mock("@/hooks/useFileContent", () => ({ triggerBrowserDownload: vi.fn() }));
vi.mock("@/hooks/useConversations", () => ({ fetchProjectSessionsPage: vi.fn() }));
beforeEach(() => vi.clearAllMocks());
it("downloads a valid ZIP using the authenticated transport", async () => {
  vi.mocked(authenticatedFetch).mockResolvedValue(
    new Response("zip", { headers: { "content-type": "application/zip" } }),
  );
  await downloadJobWorkspace("job/1");
  expect(authenticatedFetch).toHaveBeenCalledWith("/v1/sessions/job%2F1/download");
  expect(triggerBrowserDownload).toHaveBeenCalledWith(expect.any(Blob), "xwav-job-job_1.zip");
});
it("uses the latest project job, independent of sidebar pagination", async () => {
  vi.mocked(fetchProjectSessionsPage).mockResolvedValue({
    data: [{ id: "job-latest" }],
    has_more: false,
  } as never);
  vi.mocked(authenticatedFetch).mockResolvedValue(
    new Response("zip", { headers: { "content-type": "application/zip" } }),
  );
  await downloadLatestProjectWorkspace("My project");
  expect(fetchProjectSessionsPage).toHaveBeenCalledWith("My project", undefined, 1);
  expect(authenticatedFetch).toHaveBeenCalledWith("/v1/sessions/job-latest/download");
});
it("does not download a JSON error as a project ZIP", async () => {
  vi.mocked(authenticatedFetch).mockResolvedValue(
    new Response("{}", { headers: { "content-type": "application/json" } }),
  );
  await expect(downloadJobWorkspace("job")).rejects.toThrow("project ZIP");
  expect(triggerBrowserDownload).not.toHaveBeenCalled();
});
it("reports an empty project without requesting a ZIP", async () => {
  vi.mocked(fetchProjectSessionsPage).mockResolvedValue({ data: [], has_more: false } as never);
  await expect(downloadLatestProjectWorkspace("Empty")).rejects.toThrow("no active job");
  expect(authenticatedFetch).not.toHaveBeenCalled();
});

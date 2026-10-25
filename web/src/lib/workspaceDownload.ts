import { authenticatedFetch } from "@/lib/identity";
import { apiErrorFromResponse } from "@/lib/sessionsApi";
import { triggerBrowserDownload } from "@/hooks/useFileContent";
import { fetchProjectSessionsPage } from "@/hooks/useConversations";

/** Export the current saved workspace without requiring a commit or stopping the job. */
export async function downloadJobWorkspace(sessionId: string): Promise<void> {
  const response = await authenticatedFetch(
    `/v1/sessions/${encodeURIComponent(sessionId)}/download`,
  );
  if (!response.ok) throw await apiErrorFromResponse(response);
  if (!response.headers.get("content-type")?.includes("application/zip"))
    throw new Error("The server did not return a project ZIP. Refresh Xwav and retry.");
  triggerBrowserDownload(
    await response.blob(),
    `xwav-job-${sessionId.replace(/[^A-Za-z0-9_-]/g, "_").slice(0, 12)}.zip`,
  );
}

/** A project may have separate job sandboxes; export its latest active job explicitly. */
export async function downloadLatestProjectWorkspace(projectName: string): Promise<void> {
  const page = await fetchProjectSessionsPage(projectName, undefined, 1);
  const job = page.data[0];
  if (!job)
    throw new Error(
      "This project has no active job. Open an archived job to download its workspace.",
    );
  await downloadJobWorkspace(job.id);
}

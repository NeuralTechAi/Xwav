import { useQuery } from "@tanstack/react-query";
import { authenticatedFetch } from "@/lib/identity";
import { apiErrorFromResponse } from "@/lib/sessionsApi";

export interface ProjectPreviewStatus {
  state: "ready" | "starting" | "waiting" | "error";
  message: string;
  port?: number;
  revision_query?: boolean;
  version?: string;
  mode?: "hot" | "reload";
}

export function useProjectPreview(sessionId: string | null) {
  return useQuery<ProjectPreviewStatus>({
    queryKey: ["project-preview", sessionId],
    enabled: !!sessionId,
    queryFn: async ({ signal }) => {
      const response = await authenticatedFetch(
        `/v1/sessions/${encodeURIComponent(sessionId!)}/preview`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}", signal },
      );
      if (!response.ok) throw await apiErrorFromResponse(response);
      return response.json();
    },
    refetchInterval: 3000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: "always",
    refetchOnReconnect: "always",
    retry: false,
  });
}

import { expect, it, vi } from "vitest";
import { authenticatedFetch } from "./identity";
import { fetchGithubStatus } from "./githubIntegration";

vi.mock("./identity", () => ({ authenticatedFetch: vi.fn() }));
it("reports an unconfigured optional GitHub App as disabled", async () => {
  vi.mocked(authenticatedFetch).mockResolvedValue(new Response("Not found", { status: 404 }));
  expect(await fetchGithubStatus()).toMatchObject({
    enabled: false,
    connected: false,
    login: null,
  });
});
it.each([401, 403, 500])(
  "does not mistake HTTP %s for missing GitHub configuration",
  async (status) => {
    vi.mocked(authenticatedFetch).mockResolvedValue(new Response("Error", { status }));
    await expect(fetchGithubStatus()).rejects.toThrow(`GitHub status failed: ${status}`);
  },
);
it("keeps the connected account status intact", async () => {
  const status = {
    enabled: true,
    connected: true,
    login: "octocat",
    scopes: "repo",
    connected_at: 1,
    install_url: null,
  };
  vi.mocked(authenticatedFetch).mockResolvedValue(new Response(JSON.stringify(status)));
  expect(await fetchGithubStatus()).toEqual(status);
});

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SettingsExtensionsSection } from "./SettingsExtensionsSection";
import { installAgentBundle } from "@/lib/agentsApi";

const state = vi.hoisted(() => ({ enabled: true }));
vi.mock("@/lib/CapabilitiesContext", () => ({
  useServerInfo: () => ({
    agent_install: state.enabled,
    features: { custom_agents_settings_ui: true },
  }),
}));
vi.mock("@/lib/agentsApi", () => ({ installAgentBundle: vi.fn() }));
function Location() {
  return <output>{useLocation().pathname}</output>;
}
function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/settings/extensions"]}>
        <SettingsExtensionsSection />
        <Location />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return invalidate;
}
afterEach(cleanup);
beforeEach(() => {
  state.enabled = true;
  vi.mocked(installAgentBundle).mockReset();
});
const bundle = new File(["test"], "agent.tar.gz", { type: "application/gzip" });
it("offers every integration path and explains sandbox scope", () => {
  setup();
  for (const name of ["Skills", "MCP servers", "Agents", "Harness plugins"])
    expect(screen.getByRole("heading", { name })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Configure MCP tools" })).toHaveAttribute(
    "href",
    "/settings/custom-agents/new",
  );
  expect(screen.getByText(/Local host integrations do not automatically/)).toBeInTheDocument();
});
it("imports using the existing installer, refreshes agent catalogs and opens the installed agent", async () => {
  vi.mocked(installAgentBundle).mockResolvedValue({ id: "agent-123", name: "reviewer" });
  const invalidate = setup();
  fireEvent.change(screen.getByLabelText("Integration bundle"), { target: { files: [bundle] } });
  await screen.findByText("/settings/custom-agents/agent-123");
  expect(installAgentBundle).toHaveBeenCalledWith(bundle);
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["available-agents-user"] });
});
it("retains the import page and displays validation errors", async () => {
  vi.mocked(installAgentBundle).mockRejectedValue(new Error("Invalid skill frontmatter"));
  setup();
  fireEvent.change(screen.getByLabelText("Integration bundle"), { target: { files: [bundle] } });
  expect(await screen.findByRole("alert")).toHaveTextContent("Invalid skill frontmatter");
  await waitFor(() => expect(screen.getByRole("button", { name: "Import bundle" })).toBeEnabled());
});
it("does not offer writes on a server without agent installation", () => {
  state.enabled = false;
  setup();
  expect(screen.getByRole("button", { name: "Import bundle" })).toBeDisabled();
  expect(screen.queryByRole("link", { name: "Manage agents" })).toBeNull();
  expect(screen.getByRole("link", { name: "Browse installed integrations" })).toBeInTheDocument();
});

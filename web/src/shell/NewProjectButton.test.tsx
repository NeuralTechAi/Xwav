import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { createProject } from "@/lib/projectsApi";
import type * as ProjectsApi from "@/lib/projectsApi";
import { NewProjectButton } from "./NewProjectButton";

const mocks = vi.hoisted(() => ({
  hosts: [
    { host_id: "laptop", name: "This computer", status: "online" },
    { host_id: "desktop", name: "Desktop", status: "online" },
  ],
}));
vi.mock("@/hooks/useHosts", () => ({ useHosts: () => ({ data: mocks.hosts }) }));
vi.mock("@/lib/projectsApi", async (original) => ({
  ...(await original<typeof ProjectsApi>()),
  createProject: vi.fn(),
}));
vi.mock("./WorkspacePicker", () => ({
  isNavigablePath: (path: string) => path.startsWith("/"),
  WorkspacePicker: ({
    hostId,
    onSelect,
    onClose,
  }: {
    hostId: string;
    onSelect: (path: string) => void;
    onClose: () => void;
  }) => (
    <div>
      <span>Browsing {hostId}</span>
      <button type="button" onClick={() => onSelect("/projects/my-app")}>
        Choose folder
      </button>
      <button type="button" onClick={onClose}>
        Cancel browser
      </button>
    </div>
  ),
}));
afterEach(cleanup);
beforeEach(() => {
  vi.mocked(createProject).mockReset().mockResolvedValue({ id: "p1", name: "My app" });
  mocks.hosts.forEach((host) => {
    host.status = "online";
  });
});
function openDialog() {
  const onCreated = vi.fn();
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <TooltipProvider>
        <NewProjectButton onCreated={onCreated} />
      </TooltipProvider>
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByTestId("new-project"));
  fireEvent.change(screen.getByPlaceholderText("Project name…"), { target: { value: "My app" } });
  return onCreated;
}
it("atomically creates a project with the selected computer and default folder", async () => {
  const onCreated = openDialog();
  fireEvent.change(screen.getByLabelText("Source folder computer"), {
    target: { value: "desktop" },
  });
  fireEvent.click(screen.getByTestId("new-project-add-folder"));
  expect(screen.getByText("Browsing desktop")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Choose folder"));
  expect(screen.getByTestId("new-project-source-folder")).toHaveTextContent("/projects/my-app");
  fireEvent.click(screen.getByTestId("new-project-confirm"));
  await waitFor(() =>
    expect(createProject).toHaveBeenCalledWith("My app", {
      host_id: "desktop",
      workspace: "/projects/my-app",
      source_folder: true,
    }),
  );
  await waitFor(() => expect(onCreated).toHaveBeenCalledWith("My app"));
});
it("keeps empty project creation available without a source folder", async () => {
  openDialog();
  fireEvent.click(screen.getByTestId("new-project-confirm"));
  await waitFor(() => expect(createProject).toHaveBeenCalledWith("My app", undefined));
});
it("cancels folder browsing without losing the project draft", () => {
  openDialog();
  fireEvent.click(screen.getByTestId("new-project-add-folder"));
  fireEvent.click(screen.getByText("Cancel browser"));
  expect(screen.getByPlaceholderText("Project name…")).toHaveValue("My app");
  expect(screen.queryByTestId("new-project-source-folder")).toBeNull();
});
it("clears a folder when its computer changes and lets users remove a selection", async () => {
  openDialog();
  fireEvent.click(screen.getByTestId("new-project-add-folder"));
  fireEvent.click(screen.getByText("Choose folder"));
  fireEvent.change(screen.getByLabelText("Source folder computer"), {
    target: { value: "desktop" },
  });
  expect(screen.queryByTestId("new-project-source-folder")).toBeNull();
  fireEvent.click(screen.getByTestId("new-project-add-folder"));
  fireEvent.click(screen.getByText("Choose folder"));
  fireEvent.click(screen.getByLabelText("Remove source folder"));
  fireEvent.click(screen.getByTestId("new-project-confirm"));
  await waitFor(() => expect(createProject).toHaveBeenCalledWith("My app", undefined));
});
it("explains how to connect a computer when none is online", () => {
  mocks.hosts.forEach((host) => {
    host.status = "offline";
  });
  openDialog();
  expect(screen.getByTestId("new-project-add-folder")).toBeDisabled();
  expect(screen.getByText(/Connect a computer in Settings/)).toBeInTheDocument();
  expect(screen.getByTestId("new-project-confirm")).toBeEnabled();
});
it("keeps the dialog and source choice when creation fails", async () => {
  vi.mocked(createProject).mockRejectedValue(new Error("Project already exists"));
  openDialog();
  fireEvent.click(screen.getByTestId("new-project-add-folder"));
  fireEvent.click(screen.getByText("Choose folder"));
  fireEvent.click(screen.getByTestId("new-project-confirm"));
  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent("Project already exists"),
  );
  expect(screen.getByTestId("new-project-source-folder")).toHaveTextContent("/projects/my-app");
});

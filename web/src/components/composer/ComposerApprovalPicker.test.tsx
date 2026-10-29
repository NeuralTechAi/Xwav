import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { ComposerApprovalPicker } from "./ComposerApprovalPicker";

vi.mock("@/lib/identity", () => ({
  authenticatedFetch: (...args: unknown[]) => fetch(...(args as Parameters<typeof fetch>)),
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

function setup({ disabled = false, failLoad = false, failSave = false } = {}) {
  let policies: Record<string, unknown>[] = [
    { id: "other", name: "custom_safety", handler: "other", source: "session", enabled: true },
  ];
  const transport = vi.fn(async (_url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      if (failSave) return new Response("", { status: 403 });
      policies.push({
        id: "approval",
        ...JSON.parse(String(init.body)),
        source: "session",
        enabled: true,
      });
      return Response.json(policies.at(-1));
    }
    if (init?.method === "DELETE") {
      policies = policies.filter((policy) => policy.id !== "approval");
      return new Response(null, { status: 204 });
    }
    return failLoad ? new Response("", { status: 503 }) : Response.json({ data: policies });
  });
  vi.stubGlobal("fetch", transport);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <ComposerApprovalPicker
        sessionId="job"
        disabled={disabled}
        disabledReason="Only the job owner can change the approval mode"
      />
    </QueryClientProvider>,
  );
  return { transport, policies: () => policies };
}

describe("ComposerApprovalPicker", () => {
  it("persists approval policy, restores defaults, and preserves unrelated policies", async () => {
    const state = setup();
    const chip = screen.getByTestId("composer-permission-chip");
    await waitFor(() => expect(chip).toBeEnabled());
    fireEvent.keyDown(chip, { key: "ArrowDown" });
    fireEvent.click(screen.getByTestId("composer-permission-option-ask"));
    await waitFor(() => expect(chip).toHaveTextContent("Ask before tools"));
    expect(state.policies()).toHaveLength(2);
    expect(state.policies()[1]).toMatchObject({
      handler: "omnigent.policies.builtins.safety.ask_on_os_tools",
      enabled: true,
    });
    fireEvent.keyDown(chip, { key: "ArrowDown" });
    fireEvent.click(screen.getByTestId("composer-permission-option-ask"));
    await waitFor(() => expect(chip).toBeEnabled());
    expect(state.transport.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(
      1,
    );
    fireEvent.keyDown(chip, { key: "ArrowDown" });
    fireEvent.click(screen.getByTestId("composer-permission-option-default"));
    await waitFor(() => expect(chip).toHaveTextContent("Harness defaults"));
    expect(state.policies().map((policy) => policy.id)).toEqual(["other"]);
  });

  it("keeps owner-only controls disabled", async () => {
    const state = setup({ disabled: true });
    await waitFor(() => expect(state.transport).toHaveBeenCalled());
    expect(screen.getByTestId("composer-permission-chip")).toBeDisabled();
    expect(screen.getByTestId("composer-permission-chip")).toHaveAttribute(
      "title",
      "Only the job owner can change the approval mode",
    );
  });

  it("fails closed when policy loading fails", async () => {
    setup({ failLoad: true });
    await waitFor(() =>
      expect(screen.getByTestId("composer-permission-chip")).toHaveTextContent(
        "Approvals unavailable",
      ),
    );
    expect(screen.getByTestId("composer-permission-chip")).toBeDisabled();
  });

  it("does not claim a rejected change was applied", async () => {
    setup({ failSave: true });
    const chip = screen.getByTestId("composer-permission-chip");
    await waitFor(() => expect(chip).toBeEnabled());
    fireEvent.keyDown(chip, { key: "ArrowDown" });
    fireEvent.click(screen.getByTestId("composer-permission-option-ask"));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(chip).toHaveTextContent("Harness defaults");
  });
});

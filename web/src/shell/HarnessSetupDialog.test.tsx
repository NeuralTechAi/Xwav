import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { showToast } from "@/components/ui/toast";
import type { InstallHarnessResult } from "@/hooks/useHosts";
import type * as AgentLabels from "@/lib/agentLabels";
import { HarnessSetupDialog } from "./HarnessSetupDialog";

const mutateMock = vi.fn();

vi.mock("@/components/ui/toast", () => ({ showToast: vi.fn() }));
vi.mock("@/hooks/useHosts", () => ({
  useHosts: () => ({ data: [] }),
  useInstallHarness: () => ({ mutate: mutateMock }),
  useInstallingHarnesses: () => new Set(),
}));
vi.mock("@/lib/CapabilitiesContext", () => ({
  useServerInfo: () => ({
    features: { harness_install: true },
    installable_harnesses: ["claude-native"],
  }),
}));
vi.mock("@/lib/agentLabels", async (original) => ({
  ...(await original<typeof AgentLabels>()),
  useHarnessSetupSteps: () => ({
    "claude-native": [
      {
        kind: "install",
        title: "Install Claude Code",
        detail: "",
        action: "install",
        command: null,
        status_key: "installed",
      },
    ],
  }),
}));

beforeEach(() => vi.clearAllMocks());

it.each([
  [true, false, "Claude Code is ready on Laptop."],
  ["needs-auth", false, "Claude Code installed on Laptop — one more step to finish setup."],
  [undefined, true, "Installed. Couldn't check Claude Code readiness on Laptop."],
] as const)("reports install readiness %s (unknown: %s)", (readiness, unknown, message) => {
  const result: InstallHarnessResult = {
    object: "harness_install",
    harness: "claude-native",
    configured_harnesses: readiness === undefined ? {} : { "claude-native": readiness },
    ...(unknown ? { readiness_unknown: true } : {}),
    version: null,
    gateway_inference: null,
  };
  mutateMock.mockImplementation(
    (_harness, options: { onSuccess: (result: InstallHarnessResult) => void }) =>
      options.onSuccess(result),
  );
  render(
    <HarnessSetupDialog
      open
      onOpenChange={vi.fn()}
      agentName="Claude Code"
      harness="claude-native"
      host={{
        host_id: "host_1",
        name: "Laptop",
        owner: "me",
        status: "online",
        configured_harnesses: { "claude-native": "binary-missing" },
      }}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Install" }));
  expect(vi.mocked(showToast).mock.calls[0]?.[0]).toBe(message);
});

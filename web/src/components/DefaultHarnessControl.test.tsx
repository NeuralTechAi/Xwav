import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { DefaultHarnessControl } from "./DefaultHarnessControl";
import { readDefaultChatHarness } from "@/lib/defaultHarnessPreferences";

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.restoreAllMocks();
});
it("saves, changes and restores the default with an automatic reset option", () => {
  const view = render(<DefaultHarnessControl />);
  fireEvent.change(screen.getByRole("combobox", { name: "Default chat harness" }), {
    target: { value: "codex-native" },
  });
  expect(readDefaultChatHarness()).toBe("codex-native");
  expect(screen.getByRole("status")).toHaveTextContent("Default harness saved.");
  view.unmount();
  render(<DefaultHarnessControl />);
  expect(screen.getByRole("combobox")).toHaveValue("codex-native");
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "pi-native" } });
  expect(readDefaultChatHarness()).toBe("pi-native");
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "" } });
  expect(readDefaultChatHarness()).toBeNull();
});
it("shows save failures without claiming the selection was saved", () => {
  render(<DefaultHarnessControl />);
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("denied");
  });
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "codex-native" } });
  expect(screen.getByRole("status")).toHaveTextContent("Could not save");
  expect(screen.getByRole("combobox")).toHaveValue("");
});

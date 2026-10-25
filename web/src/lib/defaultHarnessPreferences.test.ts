import { afterEach, describe, expect, it, vi } from "vitest";
import { readDefaultChatHarness, writeDefaultChatHarness } from "./defaultHarnessPreferences";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});
describe("default chat harness", () => {
  it("saves, changes and clears a default independently of the last session pick", () => {
    localStorage.setItem("omnigent:last-agent-id", "last-session");
    expect(readDefaultChatHarness()).toBeNull();
    expect(writeDefaultChatHarness("codex-native")).toBe(true);
    expect(readDefaultChatHarness()).toBe("codex-native");
    expect(writeDefaultChatHarness("pi-native")).toBe(true);
    expect(readDefaultChatHarness()).toBe("pi-native");
    expect(localStorage.getItem("omnigent:last-agent-id")).toBe("last-session");
    expect(writeDefaultChatHarness(null)).toBe(true);
    expect(readDefaultChatHarness()).toBeNull();
  });
  it("rejects benchmark and unknown harnesses", () => {
    expect(writeDefaultChatHarness("harness2")).toBe(false);
    localStorage.setItem("xwav:default-chat-harness", "deleted");
    expect(readDefaultChatHarness()).toBeNull();
  });
  it("reports unavailable storage without breaking the composer", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("denied");
    });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    expect(writeDefaultChatHarness("codex-native")).toBe(false);
    expect(readDefaultChatHarness()).toBeNull();
  });
});

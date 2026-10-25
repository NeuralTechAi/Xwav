import { describe, expect, it } from "vitest";
import { composeLaunchIntent } from "./launchIntent";

describe("launch intent", () => {
  it("leaves an ordinary task unchanged", () => {
    expect(composeLaunchIntent("Fix the bug", "", false)).toBe("Fix the bug");
  });
  it("preserves the task and carries its completion condition and planning request", () => {
    const prompt = composeLaunchIntent("Fix the bug", "  Tests pass  ", true);
    expect(prompt).toContain("Fix the bug\n\nCompletion condition:\nTests pass");
    expect(prompt).toContain("Wait for my approval before editing files");
  });
});

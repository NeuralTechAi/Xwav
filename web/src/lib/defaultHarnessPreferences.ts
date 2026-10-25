import { nativeCodingAgentForHarness } from "@/lib/nativeCodingAgents";

export const DEFAULT_CHAT_HARNESS_STORAGE_KEY = "xwav:default-chat-harness";

/** Browser-local default, separate from the most recent session choice. */
export function readDefaultChatHarness(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.localStorage.getItem(DEFAULT_CHAT_HARNESS_STORAGE_KEY);
    return value ? (nativeCodingAgentForHarness(value)?.harness ?? null) : null;
  } catch {
    return null;
  }
}

/** Return whether the preference could be saved, so settings can report failure. */
export function writeDefaultChatHarness(harness: string | null): boolean {
  if (typeof window === "undefined") return false;
  const canonical = harness === null ? null : nativeCodingAgentForHarness(harness)?.harness;
  if (canonical === undefined) return false;
  try {
    if (canonical === null) window.localStorage.removeItem(DEFAULT_CHAT_HARNESS_STORAGE_KEY);
    else window.localStorage.setItem(DEFAULT_CHAT_HARNESS_STORAGE_KEY, canonical);
    return true;
  } catch {
    return false;
  }
}

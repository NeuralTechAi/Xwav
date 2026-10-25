import { QueryClient, QueryClientProvider, focusManager } from "@tanstack/react-query";
import { act, cleanup, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { authenticatedFetch } from "@/lib/identity";
import { useProjectPreview } from "./useProjectPreview";

vi.mock("@/lib/identity", () => ({ authenticatedFetch: vi.fn() }));
const fetchMock = vi.mocked(authenticatedFetch);
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  focusManager.setFocused(undefined);
  fetchMock.mockReset();
});
it("keeps syncing while unfocused and stops when the preview closes", async () => {
  vi.useFakeTimers();
  focusManager.setFocused(false);
  fetchMock.mockImplementation(
    async () =>
      new Response(JSON.stringify({ state: "ready", port: 41881, version: "v1", message: "Live" })),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const { result, unmount } = renderHook(() => useProjectPreview("job-one"), { wrapper });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10);
  });
  expect(result.current.data?.state).toBe("ready");
  const before = fetchMock.mock.calls.length;
  await act(async () => {
    await vi.advanceTimersByTimeAsync(6500);
  });
  expect(fetchMock.mock.calls.length).toBeGreaterThan(before);
  expect(fetchMock.mock.calls.every(([url]) => String(url).includes("job-one/preview"))).toBe(true);
  unmount();
  const after = fetchMock.mock.calls.length;
  await act(async () => {
    await vi.advanceTimersByTimeAsync(9000);
  });
  expect(fetchMock).toHaveBeenCalledTimes(after);
  client.clear();
});

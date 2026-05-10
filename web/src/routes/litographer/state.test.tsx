/// <reference types="vitest/globals" />
import { renderHook, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { usePositionFlush } from "./state";

// Mock the bulk PATCH so we can observe what got sent without hitting fetch.
const mutateSpy = vi.fn();
vi.mock("@/api/litographer", () => ({
  useBulkPositionUpdate: () => ({ mutate: mutateSpy, isPending: false }),
}));

function wrap() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("usePositionFlush", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mutateSpy.mockReset();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("coalesces same-id enqueues — only the last position is sent", () => {
    const { result } = renderHook(() => usePositionFlush(99), { wrapper: wrap() });

    act(() => {
      result.current.enqueue(1, 10, 10);
      result.current.enqueue(1, 20, 20);
      result.current.enqueue(1, 30, 30);
    });

    // Trigger the periodic flush.
    act(() => vi.advanceTimersByTime(300));

    expect(mutateSpy).toHaveBeenCalledTimes(1);
    expect(mutateSpy).toHaveBeenCalledWith([{ id: 1, x: 30, y: 30 }]);
  });

  it("flushNow drains immediately without waiting for the interval", () => {
    const { result } = renderHook(() => usePositionFlush(99), { wrapper: wrap() });

    act(() => {
      result.current.enqueue(7, 5, 5);
      result.current.enqueue(8, -3, -3);
      result.current.flushNow();
    });

    expect(mutateSpy).toHaveBeenCalledTimes(1);
    const arg = mutateSpy.mock.calls[0][0];
    // Order isn't guaranteed since we drain a Map; check membership.
    expect(arg).toEqual(
      expect.arrayContaining([
        { id: 7, x: 5, y: 5 },
        { id: 8, x: -3, y: -3 },
      ]),
    );
  });

  it("does not call mutate when nothing is pending", () => {
    renderHook(() => usePositionFlush(99), { wrapper: wrap() });
    act(() => vi.advanceTimersByTime(1000));
    expect(mutateSpy).not.toHaveBeenCalled();
  });
});

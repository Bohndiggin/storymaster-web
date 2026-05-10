import { useCallback, useEffect, useRef } from "react";

import { useBulkPositionUpdate, type NodePosition } from "@/api/litographer";

const FLUSH_INTERVAL_MS = 250;

/**
 * Coalesces position updates from React Flow's `onNodesChange` into one
 * batched PATCH every ~250 ms. Each call to `enqueue(id, x, y)` overwrites
 * any pending entry for that id — no point sending stale waypoints.
 *
 * Returns:
 * - `enqueue(id, x, y)`: stash a position; flush will fire on the next tick.
 * - `flushNow()`: drain the buffer immediately. Call from `onNodeDragStop`
 *   so the user sees their drag persisted as soon as they release.
 *
 * The hook owns its own setInterval lifecycle. Component teardown flushes
 * any pending writes so a navigate-away doesn't drop the user's last move.
 */
export function usePositionFlush(storylineId: number) {
  const bulk = useBulkPositionUpdate(storylineId);
  const pending = useRef<Map<number, NodePosition>>(new Map());

  const send = useCallback(() => {
    if (pending.current.size === 0) return;
    const batch = Array.from(pending.current.values());
    pending.current.clear();
    bulk.mutate(batch);
  }, [bulk]);

  // Periodic flush during drag.
  useEffect(() => {
    const id = window.setInterval(send, FLUSH_INTERVAL_MS);
    return () => {
      window.clearInterval(id);
      send(); // Final drain on unmount.
    };
  }, [send]);

  const enqueue = useCallback((nodeId: number, x: number, y: number) => {
    pending.current.set(nodeId, { id: nodeId, x, y });
  }, []);

  return { enqueue, flushNow: send };
}

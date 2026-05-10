import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type { LitographyNode, NodeConnection, NodeType } from "./types";

const NODES_KEY = (storylineId: number) => ["nodes", storylineId] as const;
const CONNS_KEY = (storylineId: number) =>
  ["connections", storylineId] as const;

export function useNodes(storylineId: number | null) {
  return useQuery({
    queryKey: storylineId != null ? NODES_KEY(storylineId) : ["nodes", "idle"],
    queryFn: () =>
      api.get<LitographyNode[]>(`/api/v1/storylines/${storylineId}/nodes`),
    enabled: storylineId != null,
  });
}

export function useConnections(storylineId: number | null) {
  return useQuery({
    queryKey: storylineId != null ? CONNS_KEY(storylineId) : ["connections", "idle"],
    queryFn: () =>
      api.get<NodeConnection[]>(`/api/v1/storylines/${storylineId}/connections`),
    enabled: storylineId != null,
  });
}

export interface NodeCreatePayload {
  name?: string;
  description?: string | null;
  node_type: NodeType;
  x_position?: number;
  y_position?: number;
}

export function useCreateNode(storylineId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: NodeCreatePayload) =>
      api.post<LitographyNode>(
        `/api/v1/storylines/${storylineId}/nodes`,
        payload,
      ),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: NODES_KEY(storylineId) }),
  });
}

export function useUpdateNode(storylineId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: number } & Partial<NodeCreatePayload>) =>
      api.patch<LitographyNode>(`/api/v1/nodes/${id}`, payload),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: NODES_KEY(storylineId) }),
  });
}

export function useDeleteNode(storylineId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete<void>(`/api/v1/nodes/${id}`),
    onSuccess: () => {
      // Cascade-delete on server takes connections and notes too; nuke
      // both caches so the UI refreshes consistently.
      qc.invalidateQueries({ queryKey: NODES_KEY(storylineId) });
      qc.invalidateQueries({ queryKey: CONNS_KEY(storylineId) });
    },
  });
}

export interface NodePosition {
  id: number;
  x: number;
  y: number;
}

/**
 * Bulk-update positions in one PATCH. Used by the canvas's drag-flush
 * debouncer (see routes/litographer/state.ts) to avoid N HTTP requests
 * during a multi-node drag.
 */
export function useBulkPositionUpdate(storylineId: number) {
  return useMutation({
    mutationFn: (positions: NodePosition[]) =>
      api.patch<void>(
        `/api/v1/storylines/${storylineId}/nodes/positions`,
        { positions },
      ),
  });
}

export function useCreateConnection(storylineId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { output_node_id: number; input_node_id: number }) =>
      api.post<NodeConnection>(
        `/api/v1/storylines/${storylineId}/connections`,
        payload,
      ),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: CONNS_KEY(storylineId) }),
  });
}

export function useDeleteConnection(storylineId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete<void>(`/api/v1/connections/${id}`),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: CONNS_KEY(storylineId) }),
  });
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type {
  Arc,
  ArcPoint,
  ArcType,
  EntityRow,
  LitographyNode,
} from "./types";

// ---------------------------------------------------------------------------
// Arc types (scoped per setting)
// ---------------------------------------------------------------------------

const arcTypesKey = (settingId: number) => ["arc-types", settingId] as const;

export function useArcTypes(settingId: number | null) {
  return useQuery({
    queryKey: settingId != null ? arcTypesKey(settingId) : ["arc-types", "idle"],
    queryFn: () => api.get<ArcType[]>(`/api/v1/settings/${settingId}/arc-types`),
    enabled: settingId != null,
  });
}

export function useCreateArcType(settingId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; description?: string | null }) =>
      api.post<ArcType>(`/api/v1/settings/${settingId}/arc-types`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: arcTypesKey(settingId) }),
  });
}

export function useUpdateArcType(settingId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: number; name?: string; description?: string | null }) =>
      api.patch<ArcType>(`/api/v1/arc-types/${id}`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: arcTypesKey(settingId) }),
  });
}

export function useDeleteArcType(settingId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete<void>(`/api/v1/arc-types/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: arcTypesKey(settingId) });
      // Deleting an arc type cascades to its arcs; nuke arcs cache too.
      qc.invalidateQueries({ queryKey: ["arcs"] });
    },
  });
}

// ---------------------------------------------------------------------------
// Arcs (scoped per storyline)
// ---------------------------------------------------------------------------

const arcsKey = (storylineId: number) => ["arcs", storylineId] as const;

export function useArcs(storylineId: number | null) {
  return useQuery({
    queryKey: storylineId != null ? arcsKey(storylineId) : ["arcs", "idle"],
    queryFn: () => api.get<Arc[]>(`/api/v1/storylines/${storylineId}/arcs`),
    enabled: storylineId != null,
  });
}

export function useArc(arcId: number | null) {
  return useQuery({
    queryKey: arcId != null ? (["arc", arcId] as const) : (["arc", "idle"] as const),
    queryFn: () => api.get<Arc>(`/api/v1/arcs/${arcId}`),
    enabled: arcId != null,
  });
}

export interface ArcWritePayload {
  title: string;
  description?: string | null;
  arc_type_id: number;
  actor_ids: number[];
}

export function useCreateArc(storylineId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ArcWritePayload) =>
      api.post<Arc>(`/api/v1/storylines/${storylineId}/arcs`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: arcsKey(storylineId) }),
  });
}

export function useUpdateArc(storylineId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...payload
    }: { id: number } & Partial<ArcWritePayload>) =>
      api.patch<Arc>(`/api/v1/arcs/${id}`, payload),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: arcsKey(storylineId) });
      qc.invalidateQueries({ queryKey: ["arc", vars.id] });
      qc.invalidateQueries({ queryKey: ["arc-points", vars.id] });
    },
  });
}

export function useDeleteArc(storylineId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete<void>(`/api/v1/arcs/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: arcsKey(storylineId) }),
  });
}

// ---------------------------------------------------------------------------
// Arc points (scoped per arc)
// ---------------------------------------------------------------------------

const arcPointsKey = (arcId: number) => ["arc-points", arcId] as const;

export function useArcPoints(arcId: number | null) {
  return useQuery({
    queryKey: arcId != null ? arcPointsKey(arcId) : ["arc-points", "idle"],
    queryFn: () => api.get<ArcPoint[]>(`/api/v1/arcs/${arcId}/points`),
    enabled: arcId != null,
  });
}

export interface ArcPointWritePayload {
  title: string;
  order_index?: number;
  description?: string | null;
  emotional_state?: string | null;
  character_relationships?: string | null;
  goals?: string | null;
  internal_conflict?: string | null;
  node_id?: number | null;
}

export function useCreateArcPoint(arcId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ArcPointWritePayload) =>
      api.post<ArcPoint>(`/api/v1/arcs/${arcId}/points`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: arcPointsKey(arcId) }),
  });
}

export function useUpdateArcPoint(arcId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: number } & Partial<ArcPointWritePayload>) =>
      api.patch<ArcPoint>(`/api/v1/arc-points/${id}`, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: arcPointsKey(arcId) }),
  });
}

export function useDeleteArcPoint(arcId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete<void>(`/api/v1/arc-points/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: arcPointsKey(arcId) }),
  });
}

// ---------------------------------------------------------------------------
// Helpers used by the arc UIs
// ---------------------------------------------------------------------------

/** Actors in a setting — for the multi-link picker on the arc edit form. */
export function useActorsForSetting(settingId: number | null) {
  return useQuery({
    queryKey:
      settingId != null
        ? (["entities", settingId, "actor"] as const)
        : (["entities", "idle"] as const),
    queryFn: () =>
      api.get<EntityRow[]>(`/api/v1/settings/${settingId}/entities/actor`),
    enabled: settingId != null,
  });
}

/** Litography nodes in a storyline — for the arc-point→node picker. */
export function useNodesForStoryline(storylineId: number | null) {
  return useQuery({
    queryKey:
      storylineId != null
        ? (["nodes", storylineId] as const)
        : (["nodes", "idle"] as const),
    queryFn: () => api.get<LitographyNode[]>(`/api/v1/storylines/${storylineId}/nodes`),
    enabled: storylineId != null,
  });
}

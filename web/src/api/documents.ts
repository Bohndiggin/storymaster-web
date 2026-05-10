import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type { Timestamped } from "./types";

export interface DocumentSummary extends Timestamped {
  id: number;
  user_id: number;
  storyline_id: number | null;
  setting_id: number | null;
  title: string;
}

export interface Document extends DocumentSummary {
  content_html: string;
  entity_map_json: string;
}

export interface DocumentWritePayload {
  title?: string;
  content_html?: string;
  entity_map_json?: string;
  storyline_id?: number | null;
  setting_id?: number | null;
}

const LIST_KEY = (storylineId: number | null, settingId: number | null) =>
  ["documents", storylineId ?? null, settingId ?? null] as const;

export function useDocuments(
  storylineId: number | null,
  settingId: number | null,
) {
  return useQuery({
    queryKey: LIST_KEY(storylineId, settingId),
    queryFn: () => {
      const params = new URLSearchParams();
      if (storylineId != null) params.set("storyline_id", String(storylineId));
      if (settingId != null) params.set("setting_id", String(settingId));
      const qs = params.toString();
      return api.get<DocumentSummary[]>(
        qs ? `/api/v1/documents?${qs}` : "/api/v1/documents",
      );
    },
  });
}

export function useDocument(documentId: number | null) {
  return useQuery({
    queryKey:
      documentId != null
        ? (["document", documentId] as const)
        : (["document", "idle"] as const),
    queryFn: () => api.get<Document>(`/api/v1/documents/${documentId}`),
    enabled: documentId != null,
  });
}

export function useCreateDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: DocumentWritePayload) =>
      api.post<Document>("/api/v1/documents", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });
}

export function useUpdateDocument(documentId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: DocumentWritePayload) =>
      api.patch<Document>(`/api/v1/documents/${documentId}`, payload),
    // Optimistically update the doc cache so the editor doesn't visibly
    // reset on a quick autosave.
    onSuccess: (data) => {
      qc.setQueryData(["document", documentId], data);
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete<void>(`/api/v1/documents/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });
}

// Storyweaver hover endpoint — re-export here so the editor doesn't reach
// across to a different module for one helper.
export interface EntityHoverDetail {
  name: string;
  details: string;
}

export interface StoryweaverEntity {
  id: string; // prefix-coded: "actor_42", "location_7", etc.
  name: string;
  type: string;
}

/** Cross-table prefix-coded entity index for the auto-tag decorator. */
export function useStoryweaverEntities(settingId: number | null) {
  return useQuery({
    queryKey:
      settingId != null
        ? (["storyweaver-entities", settingId] as const)
        : (["storyweaver-entities", "idle"] as const),
    queryFn: () =>
      api.get<StoryweaverEntity[]>(
        `/api/v1/settings/${settingId}/storyweaver/entities`,
      ),
    enabled: settingId != null,
    staleTime: 30_000,
  });
}

export function useEntityHoverDetail(
  entityType: string | null,
  entityId: number | null,
) {
  return useQuery({
    queryKey:
      entityType && entityId != null
        ? (["entity-hover", entityType, entityId] as const)
        : (["entity-hover", "idle"] as const),
    queryFn: () =>
      api.get<EntityHoverDetail>(
        `/api/v1/storyweaver/entities/${entityType}/${entityId}/details`,
      ),
    enabled: !!entityType && entityId != null,
    staleTime: 60_000,
  });
}

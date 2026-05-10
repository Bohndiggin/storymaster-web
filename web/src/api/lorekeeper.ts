import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { EntityRow, LorekeeperSchema } from "@/api/types";

import { api } from "./client";

const SCHEMA_KEY = ["lorekeeper", "schema"] as const;

export function useLorekeeperSchema() {
  return useQuery({
    queryKey: SCHEMA_KEY,
    queryFn: () => api.get<LorekeeperSchema>("/api/v1/lorekeeper/schema"),
    staleTime: 5 * 60_000, // schema rarely changes within a session
  });
}

function entityListKey(settingId: number, table: string) {
  return ["entities", settingId, table] as const;
}

export function useEntityList(settingId: number | null, table: string | null) {
  return useQuery({
    queryKey: settingId != null && table ? entityListKey(settingId, table) : ["entities", "idle"],
    queryFn: () =>
      api.get<EntityRow[]>(`/api/v1/settings/${settingId}/entities/${table}`),
    enabled: settingId != null && !!table,
  });
}

export function useEntity(settingId: number | null, table: string | null, id: number | null) {
  return useQuery({
    queryKey:
      settingId != null && table && id != null
        ? ["entity", settingId, table, id]
        : ["entity", "idle"],
    queryFn: () =>
      api.get<EntityRow>(`/api/v1/settings/${settingId}/entities/${table}/${id}`),
    enabled: settingId != null && !!table && id != null,
  });
}

export function useCreateEntity(settingId: number, table: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      api.post<EntityRow>(`/api/v1/settings/${settingId}/entities/${table}`, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: entityListKey(settingId, table) });
    },
  });
}

export function useUpdateEntity(settingId: number, table: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: number } & Record<string, unknown>) =>
      api.patch<EntityRow>(
        `/api/v1/settings/${settingId}/entities/${table}/${id}`,
        payload,
      ),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: entityListKey(settingId, table) });
      qc.invalidateQueries({ queryKey: ["entity", settingId, table, vars.id] });
    },
  });
}

export function useDeleteEntity(settingId: number, table: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      api.delete<void>(`/api/v1/settings/${settingId}/entities/${table}/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: entityListKey(settingId, table) });
    },
  });
}

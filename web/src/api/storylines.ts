import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { Setting, Storyline } from "@/api/types";

import { api } from "./client";

const STORYLINES_KEY = ["storylines"] as const;
const SETTINGS_KEY = ["settings"] as const;

export function useStorylines() {
  return useQuery({
    queryKey: STORYLINES_KEY,
    queryFn: () => api.get<Storyline[]>("/api/v1/storylines"),
  });
}

export function useSettings() {
  return useQuery({
    queryKey: SETTINGS_KEY,
    queryFn: () => api.get<Setting[]>("/api/v1/settings"),
  });
}

export function useCreateStoryline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name?: string; description?: string }) =>
      api.post<Storyline>("/api/v1/storylines", payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: STORYLINES_KEY });
    },
  });
}

export function useUpdateStoryline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: number; name?: string; description?: string }) =>
      api.patch<Storyline>(`/api/v1/storylines/${id}`, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: STORYLINES_KEY });
    },
  });
}

export function useDeleteStoryline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete<void>(`/api/v1/storylines/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: STORYLINES_KEY });
      // Storyline-scoped data (nodes, arcs, notes) is gone server-side.
      qc.invalidateQueries({ queryKey: ["litographer"] });
      qc.invalidateQueries({ queryKey: ["arcs"] });
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}

export function useCreateSetting() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name?: string; description?: string }) =>
      api.post<Setting>("/api/v1/settings", payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SETTINGS_KEY });
    },
  });
}

export function useUpdateSetting() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: number; name?: string; description?: string }) =>
      api.patch<Setting>(`/api/v1/settings/${id}`, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SETTINGS_KEY });
    },
  });
}

export function useDeleteSetting() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete<void>(`/api/v1/settings/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SETTINGS_KEY });
      // Lorekeeper entities live under settings — drop their caches too.
      qc.invalidateQueries({ queryKey: ["entities"] });
      qc.invalidateQueries({ queryKey: ["lorekeeper"] });
    },
  });
}

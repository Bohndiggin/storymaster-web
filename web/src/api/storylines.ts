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

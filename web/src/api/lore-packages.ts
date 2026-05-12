import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api } from "./client";

export interface LorePackage {
  slug: string;
  display_name: string;
  description: string;
  category: string;
  version: string;
}

export interface LorePackageImportResult {
  package: string;
  imported: number;
  skipped_duplicates: number;
  imported_by_table: Record<string, number>;
}

const LORE_PACKAGES_KEY = ["lore-packages"] as const;

export function useLorePackages() {
  return useQuery({
    queryKey: LORE_PACKAGES_KEY,
    queryFn: () => api.get<LorePackage[]>("/api/v1/lore-packages"),
  });
}

export function useImportLorePackage(settingId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => {
      if (settingId == null) {
        return Promise.reject(new Error("No setting selected"));
      }
      return api.post<LorePackageImportResult>(
        `/api/v1/settings/${settingId}/lore-packages/import`,
        { package: slug },
      );
    },
    onSuccess: () => {
      // Imported rows show up under multiple lorekeeper tables; invalidate
      // anything keyed off `entities` for this setting. Going broad here is
      // fine — imports are rare.
      qc.invalidateQueries({ queryKey: ["entities"] });
      qc.invalidateQueries({ queryKey: ["lorekeeper"] });
      qc.invalidateQueries({ queryKey: ["arcs"] });
    },
  });
}

export function useUploadLorePackage(settingId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File): Promise<LorePackageImportResult> => {
      if (settingId == null) {
        throw new Error("No setting selected");
      }
      const form = new FormData();
      form.append("file", file);
      // FormData uploads bypass the JSON `api.post` helper because we need to
      // *not* set a Content-Type header — fetch fills in the multipart
      // boundary itself.
      const res = await fetch(
        `/api/v1/settings/${settingId}/lore-packages/upload`,
        { method: "POST", credentials: "include", body: form },
      );
      const contentType = res.headers.get("content-type") ?? "";
      const data = contentType.includes("application/json")
        ? await res.json()
        : await res.text();
      if (!res.ok) {
        const detail = (data as { detail?: unknown })?.detail ?? data;
        throw new ApiError(res.status, detail);
      }
      return data as LorePackageImportResult;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["entities"] });
      qc.invalidateQueries({ queryKey: ["lorekeeper"] });
      qc.invalidateQueries({ queryKey: ["arcs"] });
    },
  });
}

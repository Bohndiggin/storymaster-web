import { useEffect } from "react";

import { api } from "@/api/client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { cn } from "@/lib/cn";

interface PlotRow {
  id: number;
  title: string;
  description: string | null;
  storyline_id: number;
  sync_uuid: string;
  created_at: string;
  updated_at: string;
  version: number;
}

interface PlotSectionRow {
  id: number;
  plot_section_type: string;
  plot_id: number;
  sync_uuid: string;
  created_at: string;
  updated_at: string;
  version: number;
}

const PLOT_SECTION_TYPE = "Tension Sustains"; // matches PlotSectionType.FLAT.value

interface PlotSectionTabsProps {
  storylineId: number;
  selectedSectionId: number | null;
  onSelect: (sectionId: number | null) => void;
}

/**
 * Top-of-canvas tab strip mirroring the desktop's section tabs.
 *
 * Behavior matches `load_plot_sections` on the desktop: if the storyline has
 * no plot/section yet, we transparently create a default Plot 1 + one FLAT
 * section so the UI has tabs to render. (The desktop does the same; the
 * server has the cascade to handle deletion.)
 */
export function PlotSectionTabs({
  storylineId,
  selectedSectionId,
  onSelect,
}: PlotSectionTabsProps) {
  const qc = useQueryClient();

  const plotsKey = ["plots", storylineId] as const;
  const plots = useQuery({
    queryKey: plotsKey,
    queryFn: () => api.get<PlotRow[]>(`/api/v1/storylines/${storylineId}/plots`),
  });

  const ensurePlot = useMutation({
    mutationFn: () =>
      api.post<PlotRow>(`/api/v1/storylines/${storylineId}/plots`, {
        title: "Plot 1",
        description: "Default plot for storyline",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: plotsKey }),
  });

  // Active plot is the first one. Plot management UI lands later; for the
  // canvas we just need *a* plot to hang sections off of.
  const activePlot = plots.data?.[0];

  // Auto-create a default plot if the storyline has none.
  useEffect(() => {
    if (plots.data && plots.data.length === 0 && !ensurePlot.isPending) {
      ensurePlot.mutate();
    }
  }, [plots.data, ensurePlot]);

  const sectionsKey = activePlot
    ? (["plot-sections", activePlot.id] as const)
    : (["plot-sections", "idle"] as const);

  const sections = useQuery({
    queryKey: sectionsKey,
    queryFn: () =>
      api.get<PlotSectionRow[]>(`/api/v1/plots/${activePlot!.id}/sections`),
    enabled: !!activePlot,
  });

  const ensureSection = useMutation({
    mutationFn: () =>
      api.post<PlotSectionRow>(`/api/v1/plots/${activePlot!.id}/sections`, {
        plot_section_type: PLOT_SECTION_TYPE,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: sectionsKey }),
  });

  const addSection = useMutation({
    mutationFn: () =>
      api.post<PlotSectionRow>(`/api/v1/plots/${activePlot!.id}/sections`, {
        plot_section_type: PLOT_SECTION_TYPE,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: sectionsKey }),
  });

  // Same default-section bootstrap.
  useEffect(() => {
    if (
      activePlot &&
      sections.data &&
      sections.data.length === 0 &&
      !ensureSection.isPending
    ) {
      ensureSection.mutate();
    }
  }, [activePlot, sections.data, ensureSection]);

  // First section becomes the default selection.
  useEffect(() => {
    if (sections.data && sections.data.length > 0 && selectedSectionId == null) {
      onSelect(sections.data[0].id);
    }
  }, [sections.data, selectedSectionId, onSelect]);

  if (!activePlot || !sections.data) {
    return (
      <div className="flex items-center gap-2 border-b border-slate-800 bg-canvas-panel px-3 py-2 text-xs text-slate-400">
        Loading plot…
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 border-b border-slate-800 bg-canvas-panel px-3 py-2">
      <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
        {activePlot.title}
      </span>
      <div className="flex flex-1 gap-1 overflow-x-auto">
        {sections.data.map((s, i) => (
          <button
            key={s.id}
            type="button"
            onClick={() => onSelect(s.id)}
            className={cn(
              "rounded-md px-3 py-1 text-xs whitespace-nowrap transition-colors",
              s.id === selectedSectionId
                ? "bg-canvas-raised text-slate-100"
                : "text-slate-400 hover:bg-canvas-raised/50",
            )}
          >
            §{i + 1} <span className="text-slate-500">{s.plot_section_type}</span>
          </button>
        ))}
      </div>
      <button
        type="button"
        onClick={() => addSection.mutate()}
        disabled={addSection.isPending}
        className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:bg-canvas-raised"
      >
        + Section
      </button>
    </div>
  );
}

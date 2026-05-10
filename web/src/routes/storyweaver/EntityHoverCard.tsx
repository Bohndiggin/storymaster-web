import { useEntityHoverDetail } from "@/api/documents";

interface EntityHoverCardProps {
  entityType: string;
  entityId: number;
  entityName: string;
}

/** Floating card body shown when the user hovers an auto-tagged span. */
export function EntityHoverCard({
  entityType,
  entityId,
  entityName,
}: EntityHoverCardProps) {
  const detail = useEntityHoverDetail(entityType, entityId);

  return (
    <div className="w-72 rounded-md border border-slate-700 bg-canvas-panel p-3 text-sm shadow-lg">
      <div className="mb-1 flex items-baseline justify-between">
        <span className="font-medium text-slate-100">
          {detail.data?.name ?? entityName}
        </span>
        <span className="text-[10px] uppercase tracking-wider text-slate-500">
          {entityType}
        </span>
      </div>
      {detail.isLoading ? (
        <p className="text-xs text-slate-500">Loading…</p>
      ) : detail.error ? (
        <p className="text-xs text-red-400">Couldn't fetch details.</p>
      ) : (
        <pre className="whitespace-pre-wrap font-sans text-xs text-slate-300">
          {detail.data?.details || "No additional details."}
        </pre>
      )}
    </div>
  );
}

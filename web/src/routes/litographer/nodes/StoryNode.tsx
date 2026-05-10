import { Handle, Position, type NodeProps } from "@xyflow/react";

import type { NodeType } from "@/api/types";
import { cn } from "@/lib/cn";

/**
 * Visuals match the desktop's per-shape rendering one-for-one:
 *  exposition  → rectangle
 *  action      → diamond (rotated square)
 *  reaction    → circle
 *  twist       → star
 *  development → hexagon
 *  other       → triangle
 *
 * All variants render at a consistent ~140×96 box so React Flow's hit-test
 * and drag math doesn't shift between types. Visual differentiation is the
 * inset clip-path, fill, and ring color.
 */

export interface StoryNodeData extends Record<string, unknown> {
  label: string;
  nodeType: NodeType;
  description: string | null;
  selected: boolean;
}

const VARIANTS: Record<
  NodeType,
  {
    label: string;
    fill: string; // tailwind background
    ring: string; // tailwind ring color
    shape: string; // clip-path utility class (defined in styles.css)
  }
> = {
  exposition: {
    label: "Exposition",
    fill: "bg-sky-500/15",
    ring: "ring-sky-400",
    shape: "story-shape-rect",
  },
  action: {
    label: "Action",
    fill: "bg-amber-500/15",
    ring: "ring-amber-400",
    shape: "story-shape-diamond",
  },
  reaction: {
    label: "Reaction",
    fill: "bg-fuchsia-500/15",
    ring: "ring-fuchsia-400",
    shape: "story-shape-circle",
  },
  twist: {
    label: "Twist",
    fill: "bg-rose-500/20",
    ring: "ring-rose-400",
    shape: "story-shape-star",
  },
  development: {
    label: "Development",
    fill: "bg-emerald-500/15",
    ring: "ring-emerald-400",
    shape: "story-shape-hex",
  },
  other: {
    label: "Other",
    fill: "bg-slate-500/15",
    ring: "ring-slate-400",
    shape: "story-shape-triangle",
  },
};

export function StoryNode({ data, selected }: NodeProps) {
  const { label, nodeType, description } = data as StoryNodeData;
  const v = VARIANTS[nodeType] ?? VARIANTS.other;

  return (
    <div className="relative">
      <Handle
        type="target"
        position={Position.Left}
        className="!h-3 !w-3 !rounded-full !border-2 !border-canvas !bg-emerald-400"
      />

      <div
        className={cn(
          "flex h-24 w-36 flex-col items-center justify-center px-3 text-center",
          v.fill,
          v.shape,
          "ring-2 ring-inset",
          selected ? v.ring : "ring-slate-700",
          "transition-all",
        )}
      >
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-300">
          {v.label}
        </span>
        <span className="mt-0.5 truncate text-sm font-medium text-slate-100">
          {label || "Untitled"}
        </span>
        {description ? (
          <span className="mt-0.5 line-clamp-2 text-[10px] text-slate-400">
            {description}
          </span>
        ) : null}
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="!h-3 !w-3 !rounded-full !border-2 !border-canvas !bg-rose-400"
      />
    </div>
  );
}

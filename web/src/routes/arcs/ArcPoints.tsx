import { useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  useArcPoints,
  useCreateArcPoint,
  useDeleteArcPoint,
  useNodesForStoryline,
  useUpdateArcPoint,
  type ArcPointWritePayload,
} from "@/api/arcs";
import type { ArcPoint } from "@/api/types";
import { Button } from "@/components/Button";
import { Card, CardHeader, CardTitle } from "@/components/Card";
import { Field } from "@/components/Field";
import { Input } from "@/components/Input";
import { Select } from "@/components/Select";
import { Textarea } from "@/components/Textarea";

interface ArcPointsListProps {
  arcId: number;
  storylineId: number;
}

export function ArcPointsList({ arcId, storylineId }: ArcPointsListProps) {
  const points = useArcPoints(arcId);
  const create = useCreateArcPoint(arcId);
  const nodes = useNodesForStoryline(storylineId);

  const [draftOpen, setDraftOpen] = useState(false);

  if (points.isLoading) {
    return (
      <Card>
        <p className="text-sm text-slate-400">Loading arc points…</p>
      </Card>
    );
  }
  if (points.error) {
    return (
      <Card>
        <p className="text-sm text-red-400">Failed to load arc points.</p>
      </Card>
    );
  }

  // Display in stored order; new points get the next slot at the end.
  const sorted = [...(points.data ?? [])].sort(
    (a, b) => a.order_index - b.order_index || a.id - b.id,
  );
  const nextIndex = sorted.length ? sorted[sorted.length - 1].order_index + 1 : 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Arc points</CardTitle>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => setDraftOpen((v) => !v)}
        >
          {draftOpen ? "Cancel" : "Add point"}
        </Button>
      </CardHeader>

      {draftOpen ? (
        <DraftRow
          arcId={arcId}
          orderIndex={nextIndex}
          nodes={nodes.data ?? []}
          onCancel={() => setDraftOpen(false)}
          onCreated={() => setDraftOpen(false)}
          isCreating={create.isPending}
        />
      ) : null}

      {sorted.length === 0 && !draftOpen ? (
        <p className="text-sm text-slate-400">No arc points yet.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {sorted.map((point) => (
            <PointRow
              key={point.id}
              arcId={arcId}
              point={point}
              nodes={nodes.data ?? []}
            />
          ))}
        </ul>
      )}
    </Card>
  );
}

interface DraftRowProps {
  arcId: number;
  orderIndex: number;
  nodes: { id: number; name: string }[];
  onCancel: () => void;
  onCreated: () => void;
  isCreating: boolean;
}

function DraftRow({
  arcId,
  orderIndex,
  nodes,
  onCancel,
  onCreated,
}: DraftRowProps) {
  const create = useCreateArcPoint(arcId);
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!title.trim()) {
      setError("Title is required.");
      return;
    }
    try {
      await create.mutateAsync({
        title: title.trim(),
        order_index: orderIndex,
      } satisfies ArcPointWritePayload);
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? `Error ${err.status}` : "Save failed.");
    }
  };

  return (
    <div className="mb-3 rounded-md border border-slate-700 bg-canvas p-3">
      <div className="flex items-end gap-2">
        <Field label="Title" htmlFor="draft-title" className="flex-1">
          <Input
            id="draft-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={`Point ${orderIndex + 1}`}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                submit();
              }
            }}
          />
        </Field>
        <Button size="sm" onClick={submit} disabled={create.isPending}>
          Add
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
      {error ? <p className="mt-1 text-xs text-red-400">{error}</p> : null}
      <p className="mt-1 text-xs text-slate-500">
        After creating, expand the row to fill in description, emotional state,
        goals, etc.{" "}
        {nodes.length === 0
          ? "(No litography nodes in this storyline yet to link to.)"
          : null}
      </p>
    </div>
  );
}

interface PointRowProps {
  arcId: number;
  point: ArcPoint;
  nodes: { id: number; name: string }[];
}

function PointRow({ arcId, point, nodes }: PointRowProps) {
  const update = useUpdateArcPoint(arcId);
  const remove = useDeleteArcPoint(arcId);

  // Local edit state initialized from the server row. Saves on blur of any
  // field — a little chatty but matches how the desktop's per-field flow
  // works and avoids a "save" button per arc point.
  const [draft, setDraft] = useState(toDraft(point));
  useEffect(() => setDraft(toDraft(point)), [point]);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const persist = async (patch: Partial<typeof draft>) => {
    setError(null);
    try {
      await update.mutateAsync({
        id: point.id,
        ...toPayloadDelta(patch),
      });
    } catch (err) {
      setError(err instanceof ApiError ? `Error ${err.status}` : "Save failed.");
    }
  };

  const onDelete = async () => {
    if (!window.confirm(`Delete point "${point.title}"?`)) return;
    await remove.mutateAsync(point.id);
  };

  const linkedNodeName =
    point.node_id != null
      ? nodes.find((n) => n.id === point.node_id)?.name ?? `node #${point.node_id}`
      : null;

  return (
    <li className="rounded-md border border-slate-800 bg-canvas-panel">
      <div className="flex items-start gap-3 p-3">
        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-canvas-raised text-xs font-semibold">
          {point.order_index}
        </div>
        <div className="flex-1">
          <input
            value={draft.title}
            onChange={(e) => setDraft({ ...draft, title: e.target.value })}
            onBlur={() => {
              if (draft.title !== point.title) persist({ title: draft.title });
            }}
            className="w-full bg-transparent text-sm font-medium text-slate-100 focus:outline-none"
          />
          {linkedNodeName ? (
            <p className="text-xs text-slate-500">linked: {linkedNodeName}</p>
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="rounded-md border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:bg-canvas-raised"
        >
          {open ? "Less" : "More"}
        </button>
        <button
          type="button"
          onClick={onDelete}
          className="rounded-md border border-red-900 px-2 py-1 text-xs text-red-300 hover:bg-red-500/10"
        >
          Delete
        </button>
      </div>

      {open ? (
        <div className="grid grid-cols-2 gap-3 border-t border-slate-800 p-3">
          <Field label="Order" htmlFor={`order-${point.id}`}>
            <Input
              id={`order-${point.id}`}
              type="number"
              value={draft.order_index}
              onChange={(e) =>
                setDraft({ ...draft, order_index: Number(e.target.value) })
              }
              onBlur={() => {
                if (draft.order_index !== point.order_index)
                  persist({ order_index: draft.order_index });
              }}
            />
          </Field>
          <Field label="Linked node" htmlFor={`node-${point.id}`}>
            <Select
              id={`node-${point.id}`}
              value={draft.node_id ?? ""}
              onChange={(e) => {
                const next = e.target.value === "" ? null : Number(e.target.value);
                setDraft({ ...draft, node_id: next });
                persist({ node_id: next });
              }}
              disabled={nodes.length === 0}
            >
              <option value="">—</option>
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.name}
                </option>
              ))}
            </Select>
          </Field>
          {(["description", "emotional_state", "character_relationships", "goals", "internal_conflict"] as const).map(
            (field) => (
              <Field
                key={field}
                label={prettyName(field)}
                htmlFor={`${field}-${point.id}`}
                className="col-span-2"
              >
                <Textarea
                  id={`${field}-${point.id}`}
                  rows={2}
                  value={(draft[field] as string | null) ?? ""}
                  onChange={(e) =>
                    setDraft({ ...draft, [field]: e.target.value })
                  }
                  onBlur={() => {
                    const current = (draft[field] as string | null) ?? "";
                    const stored = (point[field] as string | null) ?? "";
                    if (current !== stored) {
                      persist({ [field]: current === "" ? null : current });
                    }
                  }}
                />
              </Field>
            ),
          )}
          {error ? (
            <p className="col-span-2 text-xs text-red-400">{error}</p>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

interface PointDraft {
  title: string;
  order_index: number;
  description: string | null;
  emotional_state: string | null;
  character_relationships: string | null;
  goals: string | null;
  internal_conflict: string | null;
  node_id: number | null;
}

function toDraft(p: ArcPoint): PointDraft {
  return {
    title: p.title,
    order_index: p.order_index,
    description: p.description,
    emotional_state: p.emotional_state,
    character_relationships: p.character_relationships,
    goals: p.goals,
    internal_conflict: p.internal_conflict,
    node_id: p.node_id,
  };
}

function toPayloadDelta(patch: Partial<PointDraft>): Partial<ArcPointWritePayload> {
  const out: Partial<ArcPointWritePayload> = {};
  for (const [k, v] of Object.entries(patch)) {
    (out as Record<string, unknown>)[k] = v;
  }
  return out;
}

function prettyName(s: string): string {
  return s.replace(/_/g, " ");
}

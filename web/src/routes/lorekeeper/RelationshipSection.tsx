import { useMemo, useState } from "react";

import {
  useCreateEntity,
  useDeleteEntity,
  useEntityList,
  useUpdateEntity,
} from "@/api/lorekeeper";
import type { EntityRow } from "@/api/types";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Select } from "@/components/Select";

import { JunctionDetailDialog } from "./JunctionDetailDialog";
import type { InlineRelationship } from "./relationships";
import { entityLabel } from "./schema";

interface RelationshipSectionProps {
  relationship: InlineRelationship;
  parentId: number;
  parentTable: string;
  settingId: number;
}

export function RelationshipSection({
  relationship,
  parentId,
  parentTable,
  settingId,
}: RelationshipSectionProps) {
  const junction = useEntityList(settingId, relationship.junctionTable);
  const targets = useEntityList(settingId, relationship.targetTable);

  const create = useCreateEntity(settingId, relationship.junctionTable);
  const update = useUpdateEntity(settingId, relationship.junctionTable);
  const remove = useDeleteEntity(settingId, relationship.junctionTable);

  const [detailRowId, setDetailRowId] = useState<number | null>(null);

  // Junction rows that belong to this parent. The endpoint returns all rows
  // for the setting; filtering happens here because the junction table doesn't
  // accept query params yet.
  const rows = useMemo(() => {
    if (!junction.data) return [];
    return junction.data.filter(
      (r) => (r[relationship.parentFk] as number | null) === parentId,
    );
  }, [junction.data, parentId, relationship.parentFk]);

  // Targets we don't already link to (so the "Add" dropdown doesn't suggest
  // duplicates). The server allows multiple links to the same target with
  // different extras, but the common case is "one link per target".
  const linkedTargetIds = useMemo(
    () =>
      new Set(rows.map((r) => r[relationship.targetFk] as number | null)),
    [rows, relationship.targetFk],
  );
  const availableTargets = useMemo(() => {
    if (!targets.data) return [];
    const isSelfReference = relationship.targetTable === parentTable;
    return targets.data.filter((t) => {
      if (linkedTargetIds.has(t.id)) return false;
      // Self-referential junctions (location_a_id -> location_b_id, etc.)
      // shouldn't let a row link to itself.
      if (isSelfReference && t.id === parentId) return false;
      return true;
    });
  }, [
    targets.data,
    linkedTargetIds,
    relationship.targetTable,
    parentTable,
    parentId,
  ]);

  const [pendingTargetId, setPendingTargetId] = useState<string>("");

  async function addLink() {
    const targetId = Number(pendingTargetId);
    if (!Number.isFinite(targetId) || targetId <= 0) return;
    await create.mutateAsync({
      [relationship.parentFk]: parentId,
      [relationship.targetFk]: targetId,
    });
    setPendingTargetId("");
  }

  function targetName(row: EntityRow): string {
    const targetId = row[relationship.targetFk] as number | null;
    if (targetId == null) return "—";
    const target = targets.data?.find((t) => t.id === targetId);
    if (!target) return `#${targetId}`;
    return entityLabel(relationship.targetTable, target);
  }

  return (
    <section className="rounded-md border border-slate-800 bg-canvas-panel/40 p-3">
      <h3 className="mb-2 text-sm font-semibold text-slate-100">{relationship.title}</h3>

      {junction.isLoading || targets.isLoading ? (
        <p className="text-xs text-slate-500">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="text-xs text-slate-500">None linked.</p>
      ) : (
        <ul className="flex flex-col divide-y divide-slate-800">
          {rows.map((row) => (
            <RelationshipRow
              key={row.id}
              row={row}
              targetName={targetName(row)}
              extras={relationship.extras ?? []}
              onOpenDetails={() => setDetailRowId(row.id)}
              onUpdateExtra={(column, value) =>
                update.mutate({ id: row.id, [column]: value })
              }
              onRemove={() => remove.mutate(row.id)}
              removing={remove.isPending}
            />
          ))}
        </ul>
      )}

      {availableTargets.length > 0 ? (
        <div className="mt-3 flex items-center gap-2">
          <Select
            className="h-8 flex-1 text-xs"
            value={pendingTargetId}
            onChange={(e) => setPendingTargetId(e.target.value)}
            aria-label={`Add to ${relationship.title}`}
          >
            <option value="">Add…</option>
            {availableTargets.map((t) => (
              <option key={t.id} value={t.id}>
                {entityLabel(relationship.targetTable, t)}
              </option>
            ))}
          </Select>
          <Button
            size="sm"
            onClick={addLink}
            disabled={!pendingTargetId || create.isPending}
          >
            Add
          </Button>
        </div>
      ) : (
        <p className="mt-3 text-xs text-slate-500">
          {targets.data && targets.data.length === 0
            ? "No entries in the target table yet."
            : "All entries are already linked."}
        </p>
      )}

      {detailRowId != null ? (
        <JunctionDetailDialog
          tableName={relationship.junctionTable}
          rowId={detailRowId}
          settingId={settingId}
          hiddenColumns={[relationship.parentFk, relationship.targetFk]}
          title={`${
            (rows.find((r) => r.id === detailRowId) &&
              targetName(rows.find((r) => r.id === detailRowId)!)) ||
            "Link"
          } — ${relationship.title}`}
          onClose={() => setDetailRowId(null)}
        />
      ) : null}
    </section>
  );
}

interface RelationshipRowProps {
  row: EntityRow;
  targetName: string;
  extras: InlineRelationship["extras"];
  onOpenDetails: () => void;
  onUpdateExtra: (column: string, value: unknown) => void;
  onRemove: () => void;
  removing: boolean;
}

function RelationshipRow({
  row,
  targetName,
  extras,
  onOpenDetails,
  onUpdateExtra,
  onRemove,
  removing,
}: RelationshipRowProps) {
  return (
    <li className="flex items-center gap-2 py-2 text-sm">
      <button
        type="button"
        onClick={onOpenDetails}
        className="flex-1 truncate text-left text-slate-200 hover:text-accent"
      >
        {targetName}
      </button>
      {(extras ?? []).map((extra) => (
        <ExtraField
          key={extra.column}
          label={extra.label}
          inputType={extra.inputType}
          initial={row[extra.column]}
          onCommit={(v) => onUpdateExtra(extra.column, v)}
        />
      ))}
      <button
        type="button"
        onClick={onRemove}
        disabled={removing}
        aria-label="Remove link"
        className="rounded p-1 text-xs text-slate-400 hover:bg-red-500/20 hover:text-red-200 disabled:opacity-50"
      >
        ✕
      </button>
    </li>
  );
}

function ExtraField({
  label,
  inputType,
  initial,
  onCommit,
}: {
  label: string;
  inputType: "text" | "number";
  initial: unknown;
  onCommit: (value: unknown) => void;
}) {
  const initialStr = initial == null ? "" : String(initial);
  const [value, setValue] = useState(initialStr);

  function commit() {
    if (value === initialStr) return;
    if (inputType === "number") {
      const n = value === "" ? null : Number(value);
      if (n != null && !Number.isFinite(n)) return;
      onCommit(n);
    } else {
      onCommit(value === "" ? null : value);
    }
  }

  return (
    <label className="flex items-center gap-1 text-xs text-slate-400">
      <span>{label}</span>
      <Input
        type={inputType}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            (e.target as HTMLInputElement).blur();
          }
        }}
        className={inputType === "number" ? "h-7 w-16 text-xs" : "h-7 w-32 text-xs"}
      />
    </label>
  );
}

import { useEffect, useMemo, useState, type FormEvent } from "react";

import { ApiError } from "@/api/client";
import {
  useDeleteEntity,
  useEntity,
  useLorekeeperSchema,
  useUpdateEntity,
} from "@/api/lorekeeper";
import { Button } from "@/components/Button";

import {
  FieldFor,
  coerceForm,
  formatApiError,
  valueToString,
} from "./EntityForm";
import { editableColumns, type EditableColumn } from "./schema";

/**
 * Modal for editing a junction-table row's full set of fields.
 *
 * The relationship section shows just the FK + a couple of inline extras;
 * everything else (notes, status, dates, freeform descriptions) lives in
 * this dialog. The two FK columns referenced by the relationship are hidden
 * because changing them would re-link the row to a different parent/target —
 * users do that by deleting and re-adding.
 */
export interface JunctionDetailDialogProps {
  tableName: string;
  rowId: number;
  settingId: number;
  /** FK columns to hide from the form (parent + target FKs). */
  hiddenColumns?: ReadonlyArray<string>;
  /** Friendly summary shown in the header — usually `${targetName} — ${title}`. */
  title: string;
  onClose: () => void;
}

export function JunctionDetailDialog({
  tableName,
  rowId,
  settingId,
  hiddenColumns = [],
  title,
  onClose,
}: JunctionDetailDialogProps) {
  const schema = useLorekeeperSchema();
  const existing = useEntity(settingId, tableName, rowId);
  const update = useUpdateEntity(settingId, tableName);
  const remove = useDeleteEntity(settingId, tableName);

  const columns = useMemo<EditableColumn[]>(() => {
    if (!schema.data) return [];
    const t = schema.data.tables[tableName];
    if (!t) return [];
    const hidden = new Set(hiddenColumns);
    return editableColumns(t.columns).filter((c) => !hidden.has(c.name));
  }, [schema.data, tableName, hiddenColumns]);

  const [form, setForm] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (existing.data) {
      setForm(
        Object.fromEntries(
          columns.map((c) => [c.name, valueToString(existing.data![c.name])]),
        ),
      );
    }
  }, [existing.data, columns]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await update.mutateAsync({ id: rowId, ...coerceForm(form, columns) });
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? formatApiError(err) : "Save failed.");
    }
  }

  async function onDelete() {
    if (!window.confirm("Remove this link and its details?")) return;
    try {
      await remove.mutateAsync(rowId);
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? formatApiError(err) : "Delete failed.");
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="junction-detail-title"
        className="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-md border border-slate-700 bg-canvas-panel shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
          <h2 id="junction-detail-title" className="text-base font-semibold">
            {title}
          </h2>
          <Button size="sm" variant="ghost" onClick={onClose}>
            Close
          </Button>
        </header>

        <div className="flex-1 overflow-y-auto px-4 py-4">
          {schema.isLoading || existing.isLoading ? (
            <p className="text-sm text-slate-400">Loading…</p>
          ) : existing.error ? (
            <p className="text-sm text-red-400">Could not load this entry.</p>
          ) : columns.length === 0 ? (
            <p className="text-sm text-slate-400">No additional fields on this link.</p>
          ) : (
            <form
              id="junction-detail-form"
              onSubmit={submit}
              className="grid grid-cols-1 gap-4 md:grid-cols-2"
            >
              {columns.map((c) => (
                <FieldFor
                  key={c.name}
                  column={c}
                  settingId={settingId}
                  value={form[c.name] ?? ""}
                  onChange={(v) => setForm((f) => ({ ...f, [c.name]: v }))}
                />
              ))}
            </form>
          )}
        </div>

        <footer className="flex items-center justify-between border-t border-slate-800 px-4 py-3">
          <Button
            variant="danger"
            size="sm"
            onClick={onDelete}
            disabled={remove.isPending}
          >
            Remove link
          </Button>
          <div className="flex items-center gap-2">
            {error ? <span className="text-xs text-red-400">{error}</span> : null}
            <Button
              type="submit"
              form="junction-detail-form"
              size="sm"
              disabled={
                update.isPending || existing.isLoading || columns.length === 0
              }
            >
              {update.isPending ? "Saving…" : "Save"}
            </Button>
          </div>
        </footer>
      </div>
    </div>
  );
}

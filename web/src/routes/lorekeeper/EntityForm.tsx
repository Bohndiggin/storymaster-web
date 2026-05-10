import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import {
  useCreateEntity,
  useDeleteEntity,
  useEntity,
  useEntityList,
  useLorekeeperSchema,
  useUpdateEntity,
} from "@/api/lorekeeper";
import { Button } from "@/components/Button";
import { Card, CardHeader, CardTitle } from "@/components/Card";
import { Field } from "@/components/Field";
import { Input } from "@/components/Input";
import { Select } from "@/components/Select";
import { useWorkspace } from "@/lib/workspace";

import { editableColumns, entityLabel, tableLabel, type EditableColumn } from "./schema";

export function EntityFormPage() {
  const { table, id } = useParams<{ table: string; id: string }>();
  const isNew = id === "new";
  const numericId = !isNew && id ? Number(id) : null;
  const { settingId } = useWorkspace();
  const navigate = useNavigate();

  const schema = useLorekeeperSchema();
  const existing = useEntity(settingId, table ?? null, numericId);

  const [form, setForm] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const columns = useMemo<EditableColumn[]>(() => {
    if (!schema.data || !table) return [];
    const t = schema.data.tables[table];
    return t ? editableColumns(t.columns) : [];
  }, [schema.data, table]);

  // When the existing row arrives, hydrate the form. We stringify everything
  // because <input> works in strings — coercion happens at submit time.
  useEffect(() => {
    if (isNew) {
      setForm(Object.fromEntries(columns.map((c) => [c.name, ""])));
    } else if (existing.data) {
      setForm(
        Object.fromEntries(
          columns.map((c) => [c.name, valueToString(existing.data![c.name])]),
        ),
      );
    }
  }, [columns, existing.data, isNew]);

  const create = useCreateEntity(settingId ?? -1, table ?? "");
  const update = useUpdateEntity(settingId ?? -1, table ?? "");
  const remove = useDeleteEntity(settingId ?? -1, table ?? "");

  if (!table) return <Navigate to="/lorekeeper" replace />;
  if (settingId == null) {
    return (
      <Card>
        <p className="text-sm text-slate-400">Pick a setting first.</p>
      </Card>
    );
  }
  if (schema.isLoading || (!isNew && existing.isLoading)) {
    return <p className="text-sm text-slate-400">Loading…</p>;
  }
  if (!isNew && existing.error) {
    return <p className="text-sm text-red-400">Could not load this entry.</p>;
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const payload = coerceForm(form, columns);
    try {
      if (isNew) {
        const created = await create.mutateAsync(payload);
        navigate(`/lorekeeper/${table}/${created.id}`, { replace: true });
      } else if (numericId != null) {
        await update.mutateAsync({ id: numericId, ...payload });
      }
    } catch (err) {
      setError(err instanceof ApiError ? formatApiError(err) : "Save failed.");
    }
  };

  const onDelete = async () => {
    if (numericId == null) return;
    if (!window.confirm("Delete this entry?")) return;
    await remove.mutateAsync(numericId);
    navigate(`/lorekeeper/${table}`, { replace: true });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {isNew
            ? `New ${tableLabel(table)}`
            : existing.data
              ? entityLabel(table, existing.data)
              : tableLabel(table)}
        </CardTitle>
        <Link
          to={`/lorekeeper/${table}`}
          className="text-xs text-slate-400 hover:text-slate-100"
        >
          ← Back
        </Link>
      </CardHeader>
      <form onSubmit={submit} className="grid grid-cols-2 gap-4">
        {columns.map((c) => (
          <FieldFor
            key={c.name}
            column={c}
            settingId={settingId}
            value={form[c.name] ?? ""}
            onChange={(v) => setForm((f) => ({ ...f, [c.name]: v }))}
          />
        ))}
        <div className="col-span-2 flex items-center justify-between pt-2">
          <div>
            {!isNew ? (
              <Button variant="danger" size="sm" onClick={onDelete} disabled={remove.isPending}>
                Delete
              </Button>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            {error ? <span className="text-xs text-red-400">{error}</span> : null}
            <Button type="submit" disabled={create.isPending || update.isPending}>
              {isNew ? "Create" : "Save"}
            </Button>
          </div>
        </div>
      </form>
    </Card>
  );
}

interface FieldForProps {
  column: EditableColumn;
  settingId: number;
  value: string;
  onChange: (v: string) => void;
}

function FieldFor({ column, settingId, value, onChange }: FieldForProps) {
  const isLong = column.inputType === "textarea";
  return (
    <Field
      label={prettyName(column.name)}
      htmlFor={column.name}
      hint={column.nullable ? "optional" : undefined}
      className={isLong ? "col-span-2" : undefined}
    >
      {column.inputType === "textarea" ? (
        <textarea
          id={column.name}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={4}
          className="w-full rounded-md border border-slate-700 bg-canvas-panel p-3 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent"
        />
      ) : column.inputType === "checkbox" ? (
        <input
          id={column.name}
          type="checkbox"
          checked={value === "true"}
          onChange={(e) => onChange(String(e.target.checked))}
          className="h-4 w-4 accent-accent"
        />
      ) : column.inputType === "fk" && column.fk ? (
        <FkSelect
          tableName={column.fk.table}
          settingId={settingId}
          value={value}
          onChange={onChange}
          nullable={column.nullable}
        />
      ) : (
        <Input
          id={column.name}
          type={column.inputType === "number" ? "number" : "text"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </Field>
  );
}

function FkSelect({
  tableName,
  settingId,
  value,
  onChange,
  nullable,
}: {
  tableName: string;
  settingId: number;
  value: string;
  onChange: (v: string) => void;
  nullable: boolean;
}) {
  // Uses the entity-list endpoint when the FK targets a setting-scoped table;
  // for foreign keys to setting / storyline / user we just show the raw id.
  const entities = useEntityList(
    isSettingScoped(tableName) ? settingId : null,
    isSettingScoped(tableName) ? tableName : null,
  );

  if (!isSettingScoped(tableName)) {
    return (
      <Input
        type="number"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={`${tableName} id`}
      />
    );
  }
  return (
    <Select value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{nullable ? "—" : "Select…"}</option>
      {(entities.data ?? []).map((row) => (
        <option key={row.id} value={String(row.id)}>
          {entityLabel(tableName, row)}
        </option>
      ))}
    </Select>
  );
}

function isSettingScoped(table: string): boolean {
  return !["user", "storyline", "setting"].includes(table);
}

function prettyName(s: string): string {
  return s.replace(/_/g, " ");
}

function valueToString(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "boolean") return v ? "true" : "false";
  return String(v);
}

function coerceForm(
  form: Record<string, string>,
  columns: EditableColumn[],
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const c of columns) {
    const raw = form[c.name];
    if (raw === "" || raw == null) {
      // Don't send empty strings for nullable columns — let the server default
      // them. For non-nullable strings the server will validate.
      continue;
    }
    if (c.inputType === "number" || c.inputType === "fk") {
      const n = Number(raw);
      if (!Number.isFinite(n)) continue;
      out[c.name] = n;
    } else if (c.inputType === "checkbox") {
      out[c.name] = raw === "true";
    } else {
      out[c.name] = raw;
    }
  }
  return out;
}

function formatApiError(err: ApiError): string {
  const detail = err.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => (typeof d === "object" && d && "msg" in d ? (d as { msg: string }).msg : String(d))).join("; ");
  }
  return `Error ${err.status}`;
}


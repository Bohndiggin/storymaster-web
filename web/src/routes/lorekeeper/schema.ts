import type { LorekeeperColumn } from "@/api/types";

export const SERVER_MANAGED_COLUMNS = new Set([
  "id",
  "setting_id",
  "sync_uuid",
  "version",
  "created_at",
  "updated_at",
  "deleted_at",
]);

export interface EditableColumn {
  name: string;
  inputType: "text" | "textarea" | "number" | "checkbox" | "fk";
  fk?: { table: string; column: string };
  nullable: boolean;
}

export function editableColumns(columns: LorekeeperColumn[]): EditableColumn[] {
  return columns
    .filter((c) => !SERVER_MANAGED_COLUMNS.has(c.name))
    .map((c) => ({
      name: c.name,
      inputType: pickInputType(c),
      fk: c.foreign_key,
      nullable: c.nullable,
    }));
}

function pickInputType(c: LorekeeperColumn): EditableColumn["inputType"] {
  if (c.foreign_key) return "fk";
  if (c.type.includes("int")) return "number";
  if (c.type.includes("float") || c.type.includes("real") || c.type.includes("numeric"))
    return "number";
  if (c.type.includes("bool")) return "checkbox";
  // Long-form on text columns the desktop typically renders as multiline.
  if (
    /(description|notes|appearance|ideal|bond|flaw|strengths|weaknesses)$/.test(c.name)
  ) {
    return "textarea";
  }
  return "text";
}

/**
 * Display label per row. Lorekeeper entities have inconsistent name columns —
 * actors split first/last/title, locations use `name`, etc.
 */
export function entityLabel(table: string, row: Record<string, unknown>): string {
  const get = (k: string) => (typeof row[k] === "string" ? (row[k] as string) : "");
  if (table === "actor") {
    const first = get("first_name");
    const last = get("last_name");
    const title = get("title");
    const composed = [title, first, last].filter(Boolean).join(" ").trim();
    return composed || `actor #${row.id}`;
  }
  if (typeof row.name === "string" && row.name) return row.name;
  if (typeof row.title === "string" && row.title) return row.title;
  return `${table} #${row.id}`;
}

/**
 * Friendly name for a table key. The `_` suffix on `location_` / `object_` /
 * `class` is a SQLite reserved-word workaround we don't want users to see.
 */
export function tableLabel(table: string): string {
  const stripped = table.replace(/_$/, "");
  return stripped.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

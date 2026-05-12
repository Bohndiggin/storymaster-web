import { useEffect, useMemo, useState } from "react";
import { Link, Navigate, Outlet, useParams } from "react-router-dom";

import {
  useEntityList,
  useEntityLists,
  useLorekeeperSchema,
} from "@/api/lorekeeper";
import type { EntityRow } from "@/api/types";
import { Card, CardHeader, CardTitle } from "@/components/Card";
import { useWorkspace } from "@/lib/workspace";
import { cn } from "@/lib/cn";

import {
  findCategoryForTable,
  LOREKEEPER_CATEGORIES,
  type LorekeeperCategory,
} from "./categories";
import { LorekeeperImportCard } from "./ImportLorePackages";
import { INLINE_JUNCTION_TABLES } from "./relationships";
import { entityLabel, tableLabel } from "./schema";

export function LorekeeperLayout() {
  const schema = useLorekeeperSchema();
  const { table } = useParams();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close the mobile picker whenever the user picks a category — the click
  // navigated, so the picker has served its purpose.
  useEffect(() => {
    setMobileOpen(false);
  }, [table]);

  if (schema.isLoading) return <div className="text-sm text-slate-400">Loading schema…</div>;
  if (schema.error || !schema.data) {
    return <div className="text-sm text-red-400">Failed to load Lorekeeper schema.</div>;
  }

  const expanded = table ? findCategoryForTable(table)?.category ?? null : null;
  const activeLabel = expanded ? `${expanded.icon} ${expanded.label}` : "Categories";

  return (
    <div className="flex flex-col gap-4 md:grid md:grid-cols-12 md:gap-6">
      <aside className="md:col-span-3">
        <Card>
          {/* Mobile trigger — tap toggles the list. Hidden on md+. */}
          <button
            type="button"
            onClick={() => setMobileOpen((v) => !v)}
            aria-expanded={mobileOpen}
            className="flex w-full items-center justify-between text-left text-lg font-semibold tracking-tight md:hidden"
          >
            <span>{activeLabel}</span>
            <span className="text-xs text-slate-400" aria-hidden>
              {mobileOpen ? "▾" : "▸"}
            </span>
          </button>
          {/* Desktop header — always visible from md+. */}
          <CardHeader className="hidden md:mb-3 md:flex">
            <CardTitle>Categories</CardTitle>
          </CardHeader>
          <ul
            className={cn(
              "mt-3 flex-col md:mt-0 md:flex",
              mobileOpen ? "flex" : "hidden",
            )}
          >
            {LOREKEEPER_CATEGORIES.map((category) => (
              <CategoryRow
                key={category.table}
                category={category}
                activeTable={table ?? null}
                expanded={expanded === category}
              />
            ))}
          </ul>
        </Card>
      </aside>
      <section className="flex min-h-[60vh] flex-col gap-4 md:col-span-9">
        <Outlet />
      </section>
    </div>
  );
}

function CategoryRow({
  category,
  activeTable,
  expanded,
}: {
  category: LorekeeperCategory;
  activeTable: string | null;
  expanded: boolean;
}) {
  const isActive = activeTable === category.table;
  return (
    <li>
      <Link
        to={`/lorekeeper/${category.table}`}
        className={cn(
          "flex items-center gap-2 rounded px-2 py-1.5 text-sm transition-colors",
          isActive
            ? "bg-canvas-raised text-slate-100"
            : "text-slate-300 hover:bg-canvas-raised/60 hover:text-slate-100",
        )}
      >
        <span aria-hidden className="w-5 text-center">
          {category.icon}
        </span>
        <span>{category.label}</span>
      </Link>
      {expanded && category.submenu?.length ? (
        <ul className="ml-7 flex flex-col border-l border-slate-800 pl-2">
          {category.submenu
            .filter((sub) => !INLINE_JUNCTION_TABLES.has(sub.table))
            .map((sub) => (
              <li key={sub.table}>
                <Link
                  to={`/lorekeeper/${sub.table}`}
                  className={cn(
                    "block rounded px-2 py-1 text-xs transition-colors",
                    activeTable === sub.table
                      ? "bg-canvas-raised text-slate-100"
                      : "text-slate-400 hover:text-slate-100",
                  )}
                >
                  {sub.label}
                </Link>
              </li>
            ))}
        </ul>
      ) : null}
    </li>
  );
}

export function LorekeeperHome() {
  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Lorekeeper</CardTitle>
        </CardHeader>
        <p className="text-sm text-slate-400">
          Pick a table on the left to view world-building entries for the active
          setting. New rows scope to whichever setting is selected in the top bar.
        </p>
      </Card>
      <LorekeeperImportCard />
    </div>
  );
}

export function EntityListPage() {
  const { table } = useParams<{ table: string }>();
  const { settingId } = useWorkspace();
  const entities = useEntityList(settingId, table ?? null);
  const schema = useLorekeeperSchema();

  // Only junction-style tables (no name/title/first_name column) need FK
  // resolution for their labels — normal entities already have a display name.
  const isJunctionLike = useMemo(() => {
    if (!schema.data || !table) return false;
    const names = new Set((schema.data.tables[table]?.columns ?? []).map((c) => c.name));
    return !names.has("name") && !names.has("title") && !names.has("first_name");
  }, [schema.data, table]);

  // FK columns on a junction table that point at another lorekeeper table —
  // used to build readable labels ("House Naïamah → House Amaxio") instead of
  // the bare "<table> #<id>" fallback.
  const fkColumns = useMemo(() => {
    if (!isJunctionLike || !schema.data || !table) {
      return [] as Array<{ column: string; target: string }>;
    }
    const cols = schema.data.tables[table]?.columns ?? [];
    return cols
      .filter((c) => c.foreign_key && c.foreign_key.table in (schema.data?.tables ?? {}))
      .map((c) => ({ column: c.name, target: c.foreign_key!.table }));
  }, [isJunctionLike, schema.data, table]);

  const referencedTables = useMemo(
    () => Array.from(new Set(fkColumns.map((f) => f.target))),
    [fkColumns],
  );
  const relatedLists = useEntityLists(settingId, referencedTables);
  const relatedById = useMemo(() => {
    const m = new Map<string, Map<number, EntityRow>>();
    referencedTables.forEach((t, i) => {
      const rows = relatedLists[i]?.data ?? [];
      m.set(t, new Map(rows.map((r) => [r.id, r])));
    });
    return m;
  }, [referencedTables, relatedLists]);

  function rowLabel(row: EntityRow): string {
    const own = entityLabel(table!, row);
    // entityLabel falls back to "<table> #<id>" when there's no name column.
    if (!own.startsWith(`${table} #`)) return own;
    const parts = fkColumns
      .map(({ column, target }) => {
        const fkId = row[column];
        if (typeof fkId !== "number") return null;
        const targetRow = relatedById.get(target)?.get(fkId);
        return targetRow ? entityLabel(target, targetRow) : `${target} #${fkId}`;
      })
      .filter((p): p is string => !!p);
    return parts.length > 0 ? parts.join(" → ") : own;
  }

  if (!table) return <Navigate to="/lorekeeper" replace />;
  if (settingId == null) {
    return (
      <Card>
        <p className="text-sm text-slate-400">
          Select or create a setting in the top bar to start adding entities.
        </p>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>{tableLabel(table)}</CardTitle>
          <Link
            to={`/lorekeeper/${table}/new`}
            className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-slate-950 hover:bg-accent-muted"
          >
            New
          </Link>
        </CardHeader>
        {entities.isLoading ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : entities.error ? (
          <p className="text-sm text-red-400">Failed to load entries.</p>
        ) : entities.data && entities.data.length > 0 ? (
          <ul className="divide-y divide-slate-800">
            {entities.data.map((row) => (
              <li key={row.id}>
                <Link
                  to={`/lorekeeper/${table}/${row.id}`}
                  className="flex items-center justify-between py-2.5 text-sm text-slate-200 hover:text-accent"
                >
                  <span>{rowLabel(row)}</span>
                  <span className="text-xs text-slate-500">#{row.id}</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-400">No entries yet.</p>
        )}
      </Card>
    </>
  );
}

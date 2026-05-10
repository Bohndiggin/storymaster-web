import { Link, Navigate, Outlet, useParams } from "react-router-dom";

import { useEntityList, useLorekeeperSchema } from "@/api/lorekeeper";
import { Card, CardHeader, CardTitle } from "@/components/Card";
import { useWorkspace } from "@/lib/workspace";
import { cn } from "@/lib/cn";

import { entityLabel, tableLabel } from "./schema";

export function LorekeeperLayout() {
  const schema = useLorekeeperSchema();
  const { table } = useParams();

  if (schema.isLoading) return <div className="text-sm text-slate-400">Loading schema…</div>;
  if (schema.error || !schema.data) {
    return <div className="text-sm text-red-400">Failed to load Lorekeeper schema.</div>;
  }

  const tables = Object.keys(schema.data.tables).sort();

  return (
    <div className="grid grid-cols-12 gap-6">
      <aside className="col-span-3">
        <Card>
          <CardHeader>
            <CardTitle>Tables</CardTitle>
          </CardHeader>
          <ul className="flex flex-col">
            {tables.map((t) => (
              <li key={t}>
                <Link
                  to={`/lorekeeper/${t}`}
                  className={cn(
                    "block rounded px-2 py-1.5 text-sm transition-colors",
                    table === t
                      ? "bg-canvas-raised text-slate-100"
                      : "text-slate-400 hover:text-slate-100",
                  )}
                >
                  {tableLabel(t)}
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      </aside>
      <section className="col-span-9 flex min-h-[60vh] flex-col gap-4">
        <Outlet />
      </section>
    </div>
  );
}

export function LorekeeperHome() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Lorekeeper</CardTitle>
      </CardHeader>
      <p className="text-sm text-slate-400">
        Pick a table on the left to view world-building entries for the active
        setting. New rows scope to whichever setting is selected in the top bar.
      </p>
    </Card>
  );
}

export function EntityListPage() {
  const { table } = useParams<{ table: string }>();
  const { settingId } = useWorkspace();
  const entities = useEntityList(settingId, table ?? null);

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
                  <span>{entityLabel(table, row)}</span>
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

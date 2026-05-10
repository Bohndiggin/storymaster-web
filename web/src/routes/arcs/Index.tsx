import { Link, NavLink, Outlet } from "react-router-dom";

import { useArcs, useArcTypes } from "@/api/arcs";
import { Card, CardHeader, CardTitle } from "@/components/Card";
import { useWorkspace } from "@/lib/workspace";
import { cn } from "@/lib/cn";

export function ArcsLayout() {
  const { storylineId, settingId } = useWorkspace();
  const arcs = useArcs(storylineId);
  const arcTypes = useArcTypes(settingId);

  // Only show "needs setting" message if storyline is also missing — the arcs
  // page doesn't strictly need a setting, but the type picker on the new-arc
  // form does.
  if (storylineId == null) {
    return (
      <Card>
        <p className="text-sm text-slate-400">
          Pick or create a storyline in the top bar to start managing arcs.
        </p>
      </Card>
    );
  }

  const typeById = new Map((arcTypes.data ?? []).map((t) => [t.id, t.name] as const));

  return (
    <div className="grid grid-cols-12 gap-6">
      <aside className="col-span-3 flex flex-col gap-3">
        <Card>
          <CardHeader>
            <CardTitle>Arcs</CardTitle>
            <Link
              to="new"
              className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-slate-950 hover:bg-accent-muted"
            >
              New
            </Link>
          </CardHeader>
          {arcs.isLoading ? (
            <p className="text-sm text-slate-400">Loading…</p>
          ) : arcs.data && arcs.data.length > 0 ? (
            <ul className="flex flex-col">
              {arcs.data.map((arc) => (
                <li key={arc.id}>
                  <ArcLink id={arc.id}>
                    <span className="block truncate text-sm">{arc.title}</span>
                    <span className="block truncate text-xs text-slate-500">
                      {typeById.get(arc.arc_type_id) ?? `type #${arc.arc_type_id}`}
                    </span>
                  </ArcLink>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-400">No arcs yet.</p>
          )}
        </Card>
        <Link
          to="types"
          className="rounded-md border border-slate-800 px-3 py-2 text-xs text-slate-300 hover:bg-canvas-raised"
        >
          Manage arc types →
        </Link>
      </aside>
      <section className="col-span-9 flex min-h-[60vh] flex-col gap-4">
        <Outlet context={{ storylineId, settingId }} />
      </section>
    </div>
  );
}

function ArcLink({ id, children }: { id: number; children: React.ReactNode }) {
  return (
    <NavLink
      to={String(id)}
      className={({ isActive }) =>
        cn(
          "block rounded px-2 py-1.5 transition-colors",
          isActive
            ? "bg-canvas-raised text-slate-100"
            : "text-slate-300 hover:bg-canvas-raised/50",
        )
      }
    >
      {children}
    </NavLink>
  );
}

export function ArcsHome() {
  const { settingId } = useWorkspace();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Character arcs</CardTitle>
      </CardHeader>
      <p className="text-sm text-slate-400">
        Pick an arc on the left to edit it, or create a new one.{" "}
        {settingId == null ? (
          <span className="text-slate-500">
            (Heads up: creating an arc needs an arc type, which lives under a
            setting — pick or create one in the top bar.)
          </span>
        ) : null}
      </p>
    </Card>
  );
}

/** Args the outlet routes pull from useOutletContext. */
export interface ArcOutletContext {
  storylineId: number;
  settingId: number | null;
}

import { useEffect } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import {
  useCreateDocument,
  useDeleteDocument,
  useDocuments,
} from "@/api/documents";
import { Button } from "@/components/Button";
import { Card, CardHeader, CardTitle } from "@/components/Card";
import { useWorkspace } from "@/lib/workspace";
import { cn } from "@/lib/cn";

export function StoryweaverLayout() {
  const { storylineId, settingId } = useWorkspace();
  const docs = useDocuments(storylineId, settingId);
  const create = useCreateDocument();
  const remove = useDeleteDocument();
  const navigate = useNavigate();

  // Pop the user into the most recent doc on first arrival, so an empty
  // editor area doesn't greet returning users.
  useEffect(() => {
    if (docs.data && docs.data.length > 0 && location.pathname === "/storyweaver") {
      navigate(`/storyweaver/${docs.data[0].id}`, { replace: true });
    }
  }, [docs.data, navigate]);

  const onNew = async () => {
    const created = await create.mutateAsync({
      title: "Untitled",
      content_html: "<p></p>",
      storyline_id: storylineId,
      setting_id: settingId,
    });
    navigate(`/storyweaver/${created.id}`);
  };

  const onDelete = async (id: number, title: string) => {
    if (!window.confirm(`Delete document "${title}"?`)) return;
    await remove.mutateAsync(id);
    navigate("/storyweaver", { replace: true });
  };

  return (
    <div className="grid grid-cols-12 gap-6">
      <aside className="col-span-3">
        <Card>
          <CardHeader>
            <CardTitle>Documents</CardTitle>
            <Button size="sm" onClick={onNew} disabled={create.isPending}>
              New
            </Button>
          </CardHeader>
          {docs.isLoading ? (
            <p className="text-sm text-slate-400">Loading…</p>
          ) : docs.data && docs.data.length > 0 ? (
            <ul className="flex flex-col">
              {docs.data.map((doc) => (
                <li
                  key={doc.id}
                  className="group flex items-center justify-between"
                >
                  <NavLink
                    to={String(doc.id)}
                    className={({ isActive }) =>
                      cn(
                        "flex-1 truncate rounded px-2 py-1.5 text-sm transition-colors",
                        isActive
                          ? "bg-canvas-raised text-slate-100"
                          : "text-slate-300 hover:bg-canvas-raised/50",
                      )
                    }
                    title={doc.title}
                  >
                    {doc.title || "Untitled"}
                  </NavLink>
                  <button
                    type="button"
                    onClick={() => onDelete(doc.id, doc.title)}
                    className="ml-1 hidden rounded px-1.5 text-xs text-slate-500 hover:text-red-400 group-hover:inline-block"
                    aria-label={`Delete ${doc.title}`}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="flex flex-col gap-2 text-sm text-slate-400">
              <p>No documents yet.</p>
              {storylineId == null && settingId == null ? (
                <p className="text-xs text-slate-500">
                  (Heads up: pick a storyline or setting in the top bar to scope
                  new documents.)
                </p>
              ) : null}
            </div>
          )}
        </Card>
      </aside>
      <section className="col-span-9 flex min-h-[60vh] flex-col gap-4">
        <Outlet />
      </section>
    </div>
  );
}

export function StoryweaverHome() {
  return (
    <Card>
      <p className="text-sm text-slate-400">
        Pick a document on the left to start writing, or{" "}
        <Link to="" className="text-accent hover:underline">
          create a new one
        </Link>
        .
      </p>
    </Card>
  );
}

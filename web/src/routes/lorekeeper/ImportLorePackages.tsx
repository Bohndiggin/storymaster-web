import { useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import {
  useImportLorePackage,
  useLorePackages,
  useUploadLorePackage,
  type LorePackage,
  type LorePackageImportResult,
} from "@/api/lore-packages";
import { Button } from "@/components/Button";
import { Card, CardHeader, CardTitle } from "@/components/Card";
import { useWorkspace } from "@/lib/workspace";

interface ImportLorePackagesProps {
  onClose: () => void;
}

interface RunResult {
  pkg: LorePackage;
  result?: LorePackageImportResult;
  error?: string;
}

export function ImportLorePackagesDialog({ onClose }: ImportLorePackagesProps) {
  const { settingId } = useWorkspace();
  const packages = useLorePackages();
  const importMutation = useImportLorePackage(settingId);

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<RunResult[]>([]);

  function toggle(slug: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  const grouped = useMemo(() => groupByCategory(packages.data ?? []), [packages.data]);

  async function run() {
    if (settingId == null || selected.size === 0) return;
    setRunning(true);
    setResults([]);
    const pending: RunResult[] = [];
    for (const pkg of packages.data ?? []) {
      if (!selected.has(pkg.slug)) continue;
      try {
        const result = await importMutation.mutateAsync(pkg.slug);
        pending.push({ pkg, result });
      } catch (err) {
        pending.push({
          pkg,
          error: err instanceof Error ? err.message : String(err),
        });
      }
      setResults([...pending]);
    }
    setRunning(false);
    setSelected(new Set());
  }

  return (
    <Backdrop onClose={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="lore-packages-title"
        className="flex max-h-[80vh] w-full max-w-xl flex-col overflow-hidden rounded-md border border-slate-700 bg-canvas-panel shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
          <h2 id="lore-packages-title" className="text-base font-semibold">
            Import lore packages
          </h2>
          <Button size="sm" variant="ghost" onClick={onClose}>
            Close
          </Button>
        </header>

        <div className="flex-1 overflow-y-auto px-4 py-3">
          {settingId == null ? (
            <p className="text-sm text-amber-300">
              Select or create a setting first — packages import into the active setting.
            </p>
          ) : packages.isLoading ? (
            <p className="text-sm text-slate-400">Loading packages…</p>
          ) : packages.error ? (
            <p className="text-sm text-red-400">Failed to load packages.</p>
          ) : (packages.data?.length ?? 0) === 0 ? (
            <p className="text-sm text-slate-400">
              No lore packages bundled with this build.
            </p>
          ) : (
            <ul className="flex flex-col gap-4">
              {Array.from(grouped.entries()).map(([category, items]) => (
                <li key={category}>
                  <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">
                    {category}
                  </p>
                  <ul className="flex flex-col gap-1.5">
                    {items.map((pkg) => (
                      <li key={pkg.slug}>
                        <label className="flex cursor-pointer items-start gap-2 rounded p-1.5 hover:bg-canvas-raised">
                          <input
                            type="checkbox"
                            className="mt-1 accent-accent"
                            checked={selected.has(pkg.slug)}
                            onChange={() => toggle(pkg.slug)}
                            disabled={running}
                          />
                          <span className="flex-1">
                            <span className="text-sm text-slate-100">{pkg.display_name}</span>
                            {pkg.description ? (
                              <span className="block text-xs text-slate-400">
                                {pkg.description}
                              </span>
                            ) : null}
                          </span>
                          <span className="text-xs text-slate-500">v{pkg.version}</span>
                        </label>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}

          {results.length > 0 ? (
            <div className="mt-4 border-t border-slate-800 pt-3">
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">
                Results
              </p>
              <ul className="flex flex-col gap-1 text-xs">
                {results.map((r) => (
                  <li
                    key={r.pkg.slug}
                    className={r.error ? "text-red-300" : "text-slate-300"}
                  >
                    <span className="text-slate-100">{r.pkg.display_name}</span>
                    {r.error ? (
                      <> — error: {r.error}</>
                    ) : (
                      <>
                        {" "}
                        — imported {r.result!.imported}, skipped{" "}
                        {r.result!.skipped_duplicates}
                      </>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <UploadSection disabled={running} />
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-slate-800 px-4 py-3">
          {selected.size > 0 ? (
            <span className="mr-auto text-xs text-slate-400">
              {selected.size} selected
            </span>
          ) : null}
          <Button variant="ghost" size="sm" onClick={onClose} disabled={running}>
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={run}
            disabled={running || settingId == null || selected.size === 0}
          >
            {running ? "Importing…" : "Import selected"}
          </Button>
        </footer>
      </div>
    </Backdrop>
  );
}

function Backdrop({
  children,
  onClose,
}: {
  children: React.ReactNode;
  onClose: () => void;
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      {children}
    </div>
  );
}

function UploadSection({ disabled }: { disabled: boolean }) {
  const { settingId } = useWorkspace();
  const upload = useUploadLorePackage(settingId);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<LorePackageImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!file) return;
    setResult(null);
    setError(null);
    try {
      const r = await upload.mutateAsync(file);
      setResult(r);
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
    } catch (err) {
      setError(
        err instanceof ApiError
          ? typeof err.detail === "string"
            ? err.detail
            : `Upload failed (${err.status})`
          : err instanceof Error
            ? err.message
            : "Upload failed",
      );
    }
  }

  return (
    <div className="mt-4 border-t border-slate-800 pt-3">
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
        Upload your own pack
      </p>
      <p className="mb-2 text-xs text-slate-400">
        A pack is a JSON file shaped like the bundled ones (table names as
        keys, lists of rows as values). FK columns get remapped automatically
        on import.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <input
          ref={inputRef}
          type="file"
          accept="application/json,.json"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          disabled={disabled || upload.isPending || settingId == null}
          className="block w-full text-xs text-slate-300 file:mr-2 file:rounded-md file:border-0 file:bg-canvas-raised file:px-3 file:py-1.5 file:text-xs file:text-slate-100 hover:file:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        />
        <Button
          size="sm"
          onClick={submit}
          disabled={
            !file || disabled || upload.isPending || settingId == null
          }
        >
          {upload.isPending ? "Uploading…" : "Upload & import"}
        </Button>
      </div>
      {error ? (
        <p className="mt-2 text-xs text-red-300">{error}</p>
      ) : result ? (
        <p className="mt-2 text-xs text-slate-300">
          <span className="text-slate-100">{result.package}</span> — imported{" "}
          {result.imported}, skipped {result.skipped_duplicates}
        </p>
      ) : null}
    </div>
  );
}

function groupByCategory(packages: LorePackage[]): Map<string, LorePackage[]> {
  const out = new Map<string, LorePackage[]>();
  for (const pkg of packages) {
    const key = pkg.category || "General";
    const list = out.get(key) ?? [];
    list.push(pkg);
    out.set(key, list);
  }
  return out;
}

export function ImportLorePackagesButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>
        Import lore packages
      </Button>
      {open ? <ImportLorePackagesDialog onClose={() => setOpen(false)} /> : null}
    </>
  );
}

export function LorekeeperImportCard() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Lore packages</CardTitle>
        <ImportLorePackagesButton />
      </CardHeader>
      <p className="text-sm text-slate-400">
        Bulk-import bundled world-building content (races, classes, factions, …) into
        the active setting. Existing entries with the same name are skipped.
      </p>
    </Card>
  );
}

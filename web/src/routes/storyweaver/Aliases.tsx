import { useState } from "react";

import type { StoryweaverEntity } from "@/api/documents";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";

/**
 * Per-document alias map.
 *
 * Wire format: `entity_map_json` is a JSON string keyed by prefix-coded
 * entity id, with a list of alternate display names:
 *
 *   {"actor_42": ["Strider", "Ranger"], "location_7": ["The Inn"]}
 *
 * Aliases feed into the auto-tag pattern set as additional matches against
 * the *same* target id, so "Strider was here" highlights to actor_42 even
 * though the canonical name is "Aragorn".
 *
 * Format mirrors the desktop's `Document.entity_map`, so a doc round-tripped
 * through `.storyweaver` import (whenever that lands — see PHASE6_TODO.md)
 * preserves alias state.
 */

export type EntityAliasMap = Record<string, string[]>;

export function parseEntityMap(raw: string | null | undefined): EntityAliasMap {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return {};
    const out: EntityAliasMap = {};
    for (const [k, v] of Object.entries(parsed)) {
      if (Array.isArray(v)) {
        out[k] = v.filter((s): s is string => typeof s === "string");
      }
    }
    return out;
  } catch {
    return {};
  }
}

export function serializeEntityMap(map: EntityAliasMap): string {
  // Stable key ordering so saves don't churn the diff.
  const keys = Object.keys(map).sort();
  const out: EntityAliasMap = {};
  for (const k of keys) {
    if (map[k] && map[k].length) out[k] = map[k];
  }
  return JSON.stringify(out);
}

/**
 * Expand the canonical entity list with one virtual entity per alias.
 * Each virtual entity points at the same target id/type/name so the
 * AutoTag plugin's match → hover-card resolution still lands on the
 * canonical row.
 */
export function expandEntitiesWithAliases(
  entities: StoryweaverEntity[],
  aliases: EntityAliasMap,
): StoryweaverEntity[] {
  if (Object.keys(aliases).length === 0) return entities;
  const out = [...entities];
  const known = new Map(entities.map((e) => [e.id, e]));
  for (const [id, names] of Object.entries(aliases)) {
    const base = known.get(id);
    if (!base) continue; // alias references entity that's been deleted
    for (const alias of names) {
      out.push({ ...base, name: alias });
    }
  }
  return out;
}

interface AliasesPanelProps {
  entities: StoryweaverEntity[];
  aliases: EntityAliasMap;
  onChange: (next: EntityAliasMap) => void;
  onClose: () => void;
}

/**
 * Compact panel: list of entities the doc has aliases for, plus an "add
 * alias" form. Lives in a popover off the editor toolbar.
 */
export function AliasesPanel({
  entities,
  aliases,
  onChange,
  onClose,
}: AliasesPanelProps) {
  const [draftEntityId, setDraftEntityId] = useState("");
  const [draftAlias, setDraftAlias] = useState("");

  const labelById = new Map(entities.map((e) => [e.id, `${e.name} (${e.type})`]));

  const addAlias = () => {
    const id = draftEntityId.trim();
    const alias = draftAlias.trim();
    if (!id || !alias) return;
    const existing = aliases[id] ?? [];
    if (existing.includes(alias)) return; // dedupe
    onChange({ ...aliases, [id]: [...existing, alias] });
    setDraftAlias("");
  };

  const removeAlias = (id: string, alias: string) => {
    const next = (aliases[id] ?? []).filter((a) => a !== alias);
    const out = { ...aliases };
    if (next.length === 0) {
      delete out[id];
    } else {
      out[id] = next;
    }
    onChange(out);
  };

  return (
    <div className="w-96 rounded-md border border-slate-700 bg-canvas-panel p-3 shadow-xl">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
          Document aliases
        </h4>
        <button
          type="button"
          onClick={onClose}
          className="text-xs text-slate-400 hover:text-slate-100"
        >
          Close ✕
        </button>
      </div>

      <p className="mb-3 text-xs text-slate-500">
        Aliases highlight to the same entity. Saved with the document.
      </p>

      <div className="mb-3 max-h-60 overflow-y-auto">
        {Object.keys(aliases).length === 0 ? (
          <p className="text-xs text-slate-500">No aliases defined.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {Object.entries(aliases).map(([id, names]) => (
              <li key={id} className="rounded border border-slate-800 p-2">
                <div className="text-xs font-medium text-slate-200">
                  {labelById.get(id) ?? id}
                </div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {names.map((alias) => (
                    <span
                      key={alias}
                      className="inline-flex items-center gap-1 rounded-full bg-canvas-raised px-2 py-0.5 text-xs"
                    >
                      {alias}
                      <button
                        type="button"
                        onClick={() => removeAlias(id, alias)}
                        className="text-slate-500 hover:text-red-400"
                        aria-label={`Remove alias ${alias}`}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="border-t border-slate-800 pt-3">
        <div className="text-xs font-medium uppercase tracking-wider text-slate-400">
          Add alias
        </div>
        <div className="mt-1 flex flex-col gap-2">
          <select
            value={draftEntityId}
            onChange={(e) => setDraftEntityId(e.target.value)}
            className="h-8 rounded border border-slate-700 bg-canvas-panel px-2 text-xs text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent"
          >
            <option value="">Pick entity…</option>
            {entities.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name} ({e.type})
              </option>
            ))}
          </select>
          <div className="flex gap-2">
            <Input
              className="h-8 flex-1 text-xs"
              value={draftAlias}
              onChange={(e) => setDraftAlias(e.target.value)}
              placeholder="alias name"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addAlias();
                }
              }}
            />
            <Button
              size="sm"
              onClick={addAlias}
              disabled={!draftEntityId || !draftAlias}
            >
              Add
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

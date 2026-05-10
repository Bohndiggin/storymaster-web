import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";

import {
  type StoryweaverEntity,
  useDocument,
  useStoryweaverEntities,
  useUpdateDocument,
} from "@/api/documents";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Input } from "@/components/Input";
import { useWorkspace } from "@/lib/workspace";

import {
  AliasesPanel,
  type EntityAliasMap,
  expandEntitiesWithAliases,
  parseEntityMap,
  serializeEntityMap,
} from "./Aliases";
import { AutoTag, rebuildAutoTag } from "./extensions/auto-tag";
import { createEntityMention } from "./extensions/entity-mention";
import { EntityHoverCard } from "./EntityHoverCard";
import { buildSuggestionRenderer } from "./MentionSuggestion";

const AUTOSAVE_INTERVAL_MS = 800;

export function StoryweaverEditor() {
  const { id } = useParams<{ id: string }>();
  const docId = id ? Number(id) : null;
  const { settingId } = useWorkspace();
  const doc = useDocument(docId);
  const update = useUpdateDocument(docId ?? 0);
  const entities = useStoryweaverEntities(settingId);
  const navigate = useNavigate();

  const [title, setTitle] = useState("");
  const [aliases, setAliases] = useState<EntityAliasMap>({});
  const [showAliases, setShowAliases] = useState(false);

  // Mutable refs the Tiptap extensions read from. Wrapping behind callbacks
  // means swapping the entity / alias list doesn't recreate the editor.
  const entitiesRef = useRef<StoryweaverEntity[]>([]);

  // Patterns that feed AutoTag = canonical entities + alias virtuals.
  const expandedEntities = useMemo(
    () => expandEntitiesWithAliases(entities.data ?? [], aliases),
    [entities.data, aliases],
  );
  useEffect(() => {
    entitiesRef.current = expandedEntities;
  }, [expandedEntities]);

  // EntityMention is parameterized with `getEntities` so the [[ popup
  // searches the canonical list (without alias virtuals — picking an
  // alias as the canonical name would be confusing).
  const mentionEntitiesRef = useRef<StoryweaverEntity[]>([]);
  useEffect(() => {
    mentionEntitiesRef.current = entities.data ?? [];
  }, [entities.data]);

  // The editor: lifecycle keyed off the document id so navigating to a
  // different doc swaps state cleanly.
  const editor = useEditor(
    {
      extensions: [
        StarterKit.configure({
          dropcursor: { color: "#38bdf8", width: 2 },
        }),
        Placeholder.configure({ placeholder: "Start writing…" }),
        AutoTag.configure({ getEntities: () => entitiesRef.current }),
        createEntityMention({
          getEntities: () => mentionEntitiesRef.current,
          renderSuggestion: buildSuggestionRenderer(),
        }),
      ],
      content: doc.data?.content_html ?? "",
      editorProps: {
        attributes: {
          class:
            "story-prose min-h-[60vh] max-w-none focus:outline-none px-6 py-4",
        },
      },
    },
    [docId],
  );

  // Hydrate when the doc loads.
  useEffect(() => {
    if (!editor || !doc.data) return;
    if (editor.getHTML() !== doc.data.content_html) {
      editor.commands.setContent(doc.data.content_html, false);
    }
    setTitle(doc.data.title);
    setAliases(parseEntityMap(doc.data.entity_map_json));
  }, [editor, doc.data]);

  // Re-scan decorations when entities or aliases change.
  useEffect(() => {
    if (!editor) return;
    rebuildAutoTag(editor.view);
  }, [expandedEntities, editor]);

  // Autosave. Diff against last-saved snapshot to skip no-op saves and
  // prevent looping with the cache-driven hydration above. We include the
  // alias map in the same PATCH so they save in lockstep with the body.
  const lastSaved = useRef<{ title: string; html: string; entityMap: string } | null>(
    null,
  );
  useEffect(() => {
    if (!doc.data || !editor || !docId) return;
    if (lastSaved.current == null) {
      lastSaved.current = {
        title: doc.data.title,
        html: doc.data.content_html,
        entityMap: doc.data.entity_map_json ?? "{}",
      };
    }
    const t = window.setTimeout(() => {
      const html = editor.getHTML();
      const entityMap = serializeEntityMap(aliases);
      const baseline = lastSaved.current!;
      const patch: {
        title?: string;
        content_html?: string;
        entity_map_json?: string;
      } = {};
      if (title !== baseline.title) patch.title = title;
      if (html !== baseline.html) patch.content_html = html;
      if (entityMap !== baseline.entityMap) patch.entity_map_json = entityMap;
      if (Object.keys(patch).length === 0) return;
      update.mutate(patch);
      lastSaved.current = { title, html, entityMap };
    }, AUTOSAVE_INTERVAL_MS);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, aliases, editor?.state.doc, doc.data, docId]);

  // Hover popover + click-to-navigate. Attached on the editor container so
  // both auto-tag decorations *and* explicit mention spans get the same
  // behavior — they share the `data-entity-id` attribute contract.
  const containerRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<HoverState | null>(null);
  useEffect(() => {
    const root = containerRef.current;
    if (!root) return;

    const onOver = (e: MouseEvent) => {
      const target = (e.target as HTMLElement | null)?.closest?.(
        "[data-entity-id]",
      ) as HTMLElement | null;
      if (!target) {
        setHover(null);
        return;
      }
      const eid = target.getAttribute("data-entity-id");
      const type = target.getAttribute("data-entity-type");
      const name = target.getAttribute("data-entity-name") ?? "";
      if (!eid || !type) return;
      const numeric = Number(eid.split("_").slice(-1)[0]);
      const rect = target.getBoundingClientRect();
      const containerRect = root.getBoundingClientRect();
      setHover({
        entityType: type,
        entityId: numeric,
        entityName: name,
        x: rect.left - containerRect.left,
        y: rect.bottom - containerRect.top + 4,
      });
    };
    const onOut = (e: MouseEvent) => {
      const next = e.relatedTarget as Node | null;
      if (!next || !root.contains(next)) setHover(null);
    };
    const onClick = (e: MouseEvent) => {
      // Cmd/Ctrl-click an entity to navigate to its Lorekeeper page.
      // Plain click stays inside the editor so cursor placement still works.
      if (!(e.metaKey || e.ctrlKey)) return;
      const target = (e.target as HTMLElement | null)?.closest?.(
        "[data-entity-id]",
      ) as HTMLElement | null;
      if (!target) return;
      const eid = target.getAttribute("data-entity-id");
      if (!eid) return;
      const [type, numeric] = eid.split("_");
      if (!type || !numeric) return;
      e.preventDefault();
      e.stopPropagation();
      // Storyweaver prefix codes use trailing-underscore SQLite reserved-word
      // workarounds for some tables (`location_`, `object_`). The hover
      // endpoint accepts the bare prefixes; the Lorekeeper route uses the
      // raw table names.
      const lorekeeperTable = ENTITY_PREFIX_TO_TABLE[type] ?? type;
      navigate(`/lorekeeper/${lorekeeperTable}/${numeric}`);
    };

    root.addEventListener("mouseover", onOver);
    root.addEventListener("mouseout", onOut);
    root.addEventListener("click", onClick);
    return () => {
      root.removeEventListener("mouseover", onOver);
      root.removeEventListener("mouseout", onOut);
      root.removeEventListener("click", onClick);
    };
  }, [navigate]);

  if (docId == null) return null;
  if (doc.isLoading) {
    return (
      <Card>
        <p className="text-sm text-slate-400">Loading document…</p>
      </Card>
    );
  }
  if (doc.error) {
    return (
      <Card>
        <p className="text-sm text-red-400">Could not load this document.</p>
      </Card>
    );
  }

  return (
    <Card className="!p-0">
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-2">
        <Input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="border-0 bg-transparent px-1 text-base font-semibold focus:ring-0"
          placeholder="Untitled"
        />
        <div className="flex items-center gap-3">
          <div className="relative">
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setShowAliases((v) => !v)}
            >
              Aliases ({Object.keys(aliases).length})
            </Button>
            {showAliases ? (
              <div className="absolute right-0 top-full z-30 mt-2">
                <AliasesPanel
                  entities={entities.data ?? []}
                  aliases={aliases}
                  onChange={setAliases}
                  onClose={() => setShowAliases(false)}
                />
              </div>
            ) : null}
          </div>
          <SaveIndicator pending={update.isPending} />
        </div>
      </div>
      <div ref={containerRef} className="relative">
        <EditorContent editor={editor} />
        {hover ? (
          <div
            className="pointer-events-none absolute z-20"
            style={{ left: hover.x, top: hover.y }}
          >
            <div className="pointer-events-auto">
              <EntityHoverCard
                entityType={hover.entityType}
                entityId={hover.entityId}
                entityName={hover.entityName}
              />
            </div>
          </div>
        ) : null}
      </div>
      <div className="border-t border-slate-800 px-4 py-2 text-[11px] text-slate-500">
        Type <kbd className="rounded bg-canvas-raised px-1">[[</kbd> to mention an
        entity. <kbd className="rounded bg-canvas-raised px-1">⌘</kbd>-click any
        highlighted name to open it in Lorekeeper.
      </div>
    </Card>
  );
}

interface HoverState {
  entityType: string;
  entityId: number;
  entityName: string;
  x: number;
  y: number;
}

function SaveIndicator({ pending }: { pending: boolean }) {
  return (
    <span
      className={
        pending ? "text-xs text-slate-500" : "text-xs text-emerald-500/70"
      }
    >
      {pending ? "Saving…" : "Saved"}
    </span>
  );
}

// Storyweaver prefix codes don't always match Lorekeeper table names because
// SQLite reserves a few words. The Storyweaver layer uses the bare keyword
// in its prefix; Lorekeeper routes use the trailing-underscore variant.
const ENTITY_PREFIX_TO_TABLE: Record<string, string> = {
  location: "location_",
  object: "object_",
  worlddata: "world_data",
};

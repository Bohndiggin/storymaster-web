import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";

import type { StoryweaverEntity } from "@/api/documents";

/**
 * Underline ambient mentions of known entities.
 *
 * Direct port of the desktop's `MarkdownHighlighter._entity_patterns` flow:
 * compile one case-insensitive whole-word regex per entity name, scan each
 * text node, emit a ProseMirror inline decoration for every hit. The
 * decoration carries the entity id (prefix-coded) on a data-* attribute so
 * the hover popover can resolve back to a row.
 *
 * Performance considerations (from the plan):
 *  - We scan whole text nodes, not whole documents — ProseMirror gives us
 *    leaf-block iteration for free via `descendants`.
 *  - `getEntities` is a function so the editor can swap the entity list
 *    without re-creating the extension; trigger a re-scan with
 *    `rebuildAutoTag(view)`.
 *  - For *thousands* of entities, swap the regex array for an Aho-Corasick
 *    table. Tracked in PHASE6_TODO.md.
 */

export interface AutoTagOptions {
  /** Wrapping the entity list behind a function lets the editor swap it
   *  without re-creating the extension. */
  getEntities: () => StoryweaverEntity[];
  className?: string;
}

export const AUTO_TAG_KEY = new PluginKey("storyweaver-autotag");
export const AUTO_TAG_REBUILD_META = "storyweaver-autotag-rebuild";

export const AutoTag = Extension.create<AutoTagOptions>({
  name: "autoTag",

  addOptions() {
    return {
      getEntities: () => [],
      className: "story-entity-mention",
    };
  },

  addProseMirrorPlugins() {
    const options = this.options;
    return [
      new Plugin({
        key: AUTO_TAG_KEY,
        state: {
          init: (_, { doc }) => buildDecorations(doc, options),
          apply: (tr, old) => {
            if (tr.getMeta(AUTO_TAG_REBUILD_META)) {
              return buildDecorations(tr.doc, options);
            }
            if (tr.docChanged) {
              return buildDecorations(tr.doc, options);
            }
            return old.map(tr.mapping, tr.doc);
          },
        },
        props: {
          decorations(state) {
            return this.getState(state);
          },
        },
      }),
    ];
  },
});

function buildDecorations(
  doc: import("@tiptap/pm/model").Node,
  options: AutoTagOptions,
): DecorationSet {
  const patterns = compilePatterns(options.getEntities());
  if (patterns.length === 0) return DecorationSet.empty;

  const decos: Decoration[] = [];
  doc.descendants((node, pos, parent) => {
    // Don't re-decorate text that's already inside an explicit mention —
    // the mention node owns its own visible style and click handling.
    if (parent && parent.type.name === "entityMention") return false;
    if (!node.isText || !node.text) return;
    for (const { regex, id, type, name } of patterns) {
      regex.lastIndex = 0;
      let match: RegExpExecArray | null;
      // eslint-disable-next-line no-cond-assign
      while ((match = regex.exec(node.text)) !== null) {
        const from = pos + match.index;
        const to = from + match[0].length;
        decos.push(
          Decoration.inline(from, to, {
            class: options.className!,
            "data-entity-id": id,
            "data-entity-type": type,
            "data-entity-name": name,
          }),
        );
      }
    }
  });
  return DecorationSet.create(doc, decos);
}

interface CompiledPattern {
  regex: RegExp;
  id: string;
  type: string;
  name: string;
}

function compilePatterns(entities: StoryweaverEntity[]): CompiledPattern[] {
  // Sort longer names first so "Aragorn the King" wins over "Aragorn" when
  // both are present (matches the desktop's existing behavior).
  const sorted = [...entities].sort((a, b) => b.name.length - a.name.length);
  return sorted
    .filter((e) => e.name && e.name.trim().length >= 2)
    .map((e) => {
      // Possessive 's optional, whole-word boundary, case-insensitive.
      // Mirrors `MarkdownHighlighter._entity_patterns`.
      const escaped = e.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      return {
        regex: new RegExp(`\\b${escaped}(?:'s)?\\b`, "gi"),
        id: e.id,
        type: e.type,
        name: e.name,
      };
    });
}

/** Trigger a re-scan when the upstream entity list changes. */
export function rebuildAutoTag(view: import("@tiptap/pm/view").EditorView): void {
  view.dispatch(view.state.tr.setMeta(AUTO_TAG_REBUILD_META, true));
}

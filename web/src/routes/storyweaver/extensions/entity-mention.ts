import Mention from "@tiptap/extension-mention";
import type { SuggestionOptions } from "@tiptap/suggestion";

import type { StoryweaverEntity } from "@/api/documents";

/**
 * Configurable factory for the `EntityMention` node.
 *
 * Wraps Tiptap's prebuilt `Mention` node with a `[[` trigger and our
 * structured `data-entity-id`/`data-entity-type` HTML serialization so an
 * explicitly-tagged entity survives a save→load round trip without relying
 * on the auto-tagger to re-discover it.
 *
 * `getEntities` is a callback so the editor can swap the entity list
 * without reconfiguring the extension (same pattern as `auto-tag.ts`).
 *
 * `renderSuggestion` is a function the editor passes in to render and
 * position the popup; we keep it abstract here so this module stays
 * dependency-free aside from Tiptap.
 */

export interface EntityMentionOptions {
  getEntities: () => StoryweaverEntity[];
  renderSuggestion: SuggestionOptions["render"];
}

export interface MentionItem {
  id: string;
  label: string;
  type: string;
}

export function createEntityMention({
  getEntities,
  renderSuggestion,
}: EntityMentionOptions) {
  return Mention.extend({
    name: "entityMention",
    renderText({ node }) {
      // Used when the editor exports plaintext (e.g. for copy/paste fallback).
      const label = node.attrs.label || node.attrs.id || "?";
      return `[[${label}]]`;
    },
    renderHTML({ node, HTMLAttributes }) {
      const id = String(node.attrs.id ?? "");
      const [type] = id.split("_");
      return [
        "span",
        {
          ...HTMLAttributes,
          "data-entity-id": id,
          "data-entity-type": type,
          "data-entity-name": node.attrs.label ?? "",
        },
        node.attrs.label ?? id,
      ];
    },
    parseHTML() {
      return [
        {
          tag: "span[data-entity-id]",
          getAttrs: (el: HTMLElement | string) => {
            if (typeof el === "string" || !(el instanceof HTMLElement)) return false;
            const id = el.getAttribute("data-entity-id");
            if (!id) return false;
            return {
              id,
              label: el.getAttribute("data-entity-name") || el.textContent || "",
            };
          },
        },
      ];
    },
  }).configure({
    HTMLAttributes: {
      class: "story-mention",
    },
    suggestion: {
      char: "[[",
      command: ({ editor, range, props }) => {
        // Replace the trigger range with the mention node + a trailing space.
        editor
          .chain()
          .focus()
          .insertContentAt(range, [
            { type: "entityMention", attrs: props },
            { type: "text", text: " " },
          ])
          .run();
      },
      items: ({ query }) => {
        const q = query.trim().toLowerCase();
        const all = getEntities();
        const filtered = q
          ? all.filter((e) => e.name.toLowerCase().includes(q))
          : all;
        return filtered.slice(0, 8).map(
          (e): MentionItem => ({ id: e.id, label: e.name, type: e.type }),
        );
      },
      render: renderSuggestion,
    },
  });
}

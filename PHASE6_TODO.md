# Phase 6 — Storyweaver: remaining work

Phase 6 is **closed for v1**. What ships:

- Document CRUD + per-user / per-storyline / per-setting scoping
- TipTap editor with debounced autosave (title + content_html + entity_map_json)
- Auto-tag decoration: regex-per-entity, longest-name-first, possessive-aware,
  whole-word — direct port of the desktop's `MarkdownHighlighter`
- `EntityMention` mark with `[[`-trigger suggestion popup, structured
  `data-entity-id`/`data-entity-type` HTML serialization that survives a
  save→load round trip, and a styled "explicit mention" pill (visually
  distinct from the dashed-underline ambient highlight)
- Hover popover on every `[data-entity-id]` element (auto-tag matches and
  explicit mentions share the contract)
- ⌘/Ctrl-click any entity to navigate to its Lorekeeper page; prefix-coded
  ids re-mapped to SQLite-reserved-word table names (`location_`, `object_`,
  `world_data`)
- Per-document aliases: parse/serialize helpers, `expandEntitiesWithAliases`
  feeds the auto-tagger, panel UI from the editor toolbar, atomic save
  alongside content
- Mobile sync: `Document` registered in `ENTITY_TYPE_MAP`, pulls/pushes via
  the existing `SyncEngine`
- Cross-tenant boundary tests: hover endpoint and Lorekeeper-side fetch
  both 404 for entities in other users' settings; alias map round-trips
  through PATCH→GET unmodified

## Genuinely deferred

These are real gaps but each is a self-contained mini-project rather than
something to bolt onto the v1 slice.

### `.storyweaver` ZIP import / export

The desktop stores documents as ZIP files containing a markdown body and a
JSON metadata blob. The web port stores HTML in the database. Importing
needs a markdown→HTML converter (and a custom mention-recognition pass for
`[[Display Name|entity_id]]` syntax); exporting needs the reverse plus the
ZIP packaging. Sketch:

- Server: `POST /api/v1/documents/import` accepts a multipart upload, calls
  the desktop's existing `Document` reader (already in
  `storymaster/models/document.py`), writes a new row.
- Server: `GET /api/v1/documents/{id}/export` returns a `.storyweaver` ZIP.
- Editor: an "Import" affordance in the document list + per-doc "Export".
- Markdown↔HTML: `tiptap-markdown` works for body prose; the EntityMention
  serialization needs a hand-rolled rule on both ends.

### Aho-Corasick replacement

The current `compilePatterns` builds N regexes and runs each across every
text node on every doc-changed transaction. The desktop pays a real perf
cost here for hundreds of entities; the web port has the same algorithm.

When this bites: swap to a single Aho-Corasick automaton built from the
entity name list. `mnemonist`'s `AhoCorasick` is small and works in a
browser; rolling our own is ~80 lines. The `compilePatterns` boundary in
`auto-tag.ts` is already isolated — replace its body and add a memoization
key on the entity-list reference.

### Per-paragraph re-tagging

The plugin re-scans the whole document on every doc change. For docs over
~5k words this becomes noticeable. Better: on each transaction, compute
the changed range from `tr.steps[0]?.from..to`, walk only the enclosing
block(s), and merge the new decorations into the existing set via
`DecorationSet.add/remove`. Defer until perf bites.

### Real popover positioner

The hover card is positioned via `getBoundingClientRect`; it can clip at
viewport edges. Tippy.js or a small floating-ui binding would handle that
cleanly. Same for the `[[`-suggestion popup. Low-priority polish.

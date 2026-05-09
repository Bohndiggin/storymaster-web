# Storymaster Web Migration Plan

Convert the existing PySide6 desktop app at `../storymaster` into a webapp with a Python backend and React frontend, while keeping the desktop app working against the same shared backend.

## Constraints

1. **Deployment**: small team / shared instance. A handful of known users on one server. Real auth (login + per-user data isolation), but no public sign-up flow. SQLite acceptable to start; Postgres should be a feasible later swap.
2. **Desktop app**: KEEP IT. Desktop and webapp share one backend. Desktop is refactored to talk to the same HTTP API. Hard constraint — no plan that orphans or duplicates the desktop app.
3. **Real-time**: none. Single user at a time. Standard REST. No WebSockets, no CRDTs.

## Codebase reality check

A few things in the existing project's CLAUDE.md don't match the code; the plan is written against the actual code:

1. **No actual `intervaltree` use.** It's listed in `requirements.txt` but no code imports it. The Storyweaver "auto-tagging" in `storymaster/view/storyweaver/text_editor.py` (~2,240 lines) is a `MarkdownHighlighter(QSyntaxHighlighter)` that compiles **one regex per entity name** (`\bName(?:'s)?\b`, case-insensitive) and runs them block-by-block in `highlightBlock`. Aliases live in document metadata (`storymaster/models/document.py`) — the `.storyweaver` ZIP — not in the database. Materially easier to port than CLAUDE.md implied.
2. **`storymaster/view/litographer/litographer.py` is dead UI scaffolding** (51 lines of generated `Ui_LitographerWindow` stub, never used in earnest). The actual canvas — `ConnectionPoint`, `NodeMixin`, the per-shape node classes (`RectangleNodeItem`, `CircleNodeItem`, `DiamondNodeItem`, `StarNodeItem`, `HexagonNodeItem`, `TriangleNodeItem`), `AddNodeButton`, `DeleteNodeButton`, plus rendering and drag/connection handlers — is all in `storymaster/controller/common/main_page_controller.py` (4,959 lines). The controller is heavily Qt-coupled.
3. **`BaseModel` (`storymaster/model/common/common_model.py`, 1,023 lines) is almost entirely pure data ops.** It owns SQLAlchemy sessions, has the `_table_to_class_map`, and exposes generic CRUD plus narrative-specific methods. **It survives the refactor essentially as-is** — this is the load-bearing seam between desktop and web.
4. **There's already a working FastAPI server** (`storymaster/sync_server/`) on port 8765 with bearer-token auth, a `SyncEngine` (`sync_engine.py`, 599 lines) that handles `sync_uuid`-based upsert/conflict detection, and a `SyncClient` in `storymaster/sync_client/client.py`. **Auth is per-device, not per-user.** The schema's `User` table has `username` only — **no password column.**
5. **All `BaseTable` rows already have `sync_uuid`, `created_at`, `updated_at`, `deleted_at`, `version`.** The schema is sync-ready.
6. **Per-user data scoping is already in place** at the SQLAlchemy layer — `Storyline.user_id`, `Setting.user_id`. Lorekeeper entities scope under `Setting`. Per-user isolation falls out for free once auth is wired in.
7. **Tests are mostly model/controller-focused** with CSV fixtures (`tests/model/database/test_data/`), plus a meaningful set of sync tests. View tests are `QApplication`-dependent and routinely skipped on headless CI. Most controller tests pass through `BaseModel`, which is the part that survives.

## Top-level recommendations

- **Backend**: extend the existing FastAPI app. Don't add Flask/Django — duplicate work and two HTTP servers. Add a CRUD/REST surface alongside the existing `/api/sync/*` and `/api/pair/*` endpoints. Same uvicorn process.
- **Auth**: server-side sessions (HTTP-only cookies) + Argon2 password hashes on the `User` table. Admin creates accounts via CLI; no public sign-up. JWT is overkill for a few-user single-server deploy and is hostile to logout/revocation.
- **Desktop refactor**: ship a `BaseModelClient` that mirrors `BaseModel`'s public surface but speaks HTTP. Inject it where `BaseModel` is currently constructed. Most controllers don't touch SQLAlchemy directly — they go through `BaseModel`. The remaining direct-SQL spots in `main_page_controller.py` (e.g. `ConnectionPoint.create_connection`, `draw_connections`) move behind new `BaseModel` methods first, then the whole `BaseModel` gets a remote variant.
- **Frontend canvas**: **React Flow** for Litographer. Built-in node/edge model, drag, custom node types, minimap, pan/zoom — exactly what's hand-rolled in `QGraphicsScene` today. Each `NodeType` enum value maps to a custom node component. Edges = `node_connection` rows.
- **Rich text editor**: **TipTap.** First-class node/mark extensions for what auto-tag needs (an "EntityMention" mark with `entityId`/`entityType`), a usable suggestion plugin for `[[`-style autocomplete, and decorators for ambient name-matching highlighting. Lexical is solid but more boilerplate; Slate is lower-level than this project needs.
- **Component library**: **shadcn/ui + Tailwind.** Copy-into-repo so you own the components — good for a small team. Avoids the "Material everywhere" feel; matches the dark-theme aesthetic the desktop already has.
- **Layout**: one repo (monorepo) for the migration. Python backend stays where it is; new `web/` directory at the project root for the React app. Build artifacts get served by FastAPI's `StaticFiles` in production.
- **Sync server**: fold into the new API as `/api/v1/sync/*`. The mobile sync protocol stays (it's working, schema doesn't need to change), but it now lives next to the regular CRUD endpoints under a unified auth model. Mobile devices keep their bearer-token pairing flow; web users get sessions.

## Phased plan

Each phase leaves the project in a working state. No phase rewrites everything at once.

---

### Phase 0 — Discovery / decisions (no code, ~1 day)

**Deliverables**
- Confirm decisions: FastAPI extension (not new framework), session auth, React Flow, TipTap, monorepo, SQLite-now-Postgres-later.
- Pick session backend: `starlette-session` or `fastapi-users` minus its registration/JWT pieces (only want session middleware), or a tiny custom middleware backed by `itsdangerous` cookies — requirements are small.
- Pick a migration tool: **Alembic.** The schema currently has no migrations — `scripts/migrate_*.py` are one-shot Python scripts. Need Alembic in place before Postgres ever happens.
- Decide where the React app lives: `web/` at repo root.

**Risks**
- None at this phase, but skipping Alembic is the kind of debt that becomes painful in Phase 5.

---

### Phase 1 — Backend skeleton + auth (1–2 weeks)

**Goal**: real auth that works for both web (sessions) and desktop (now also a client). No frontend yet. Existing desktop still works unchanged.

**Files to add**
- `storymaster/api/__init__.py`
- `storymaster/api/app.py` — new top-level FastAPI app that mounts the existing `sync_server` app (preserve `/api/pair/*`, `/api/sync/*` routes). Or merge routers — recommended.
- `storymaster/api/auth.py` — `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`. Argon2 via `argon2-cffi`. Sessions stored server-side keyed by a cookie session ID; for one server SQLite-backed sessions are fine (a `user_session` table).
- `storymaster/api/deps.py` — `get_current_user(request) -> User` dependency. Reads session cookie OR Bearer token (so mobile keeps working).
- `storymaster/api/main.py` — uvicorn entry point that replaces `start_sync_server.py`.
- `scripts/create_admin.py` — CLI to add the first user (prompts for password, stores Argon2 hash).
- `alembic/` — Alembic init + initial baseline matching current schema, plus migration adding `User.password_hash`, `User.is_active`, `user_session`.

**Files to modify**
- `storymaster/model/database/schema/base.py` — add `password_hash: Mapped[str|None]`, `is_active: Mapped[bool]` on `User`. Add a `UserSession` model.
- `storymaster/sync_server/main.py` — protect `/api/sync/*` such that requests must be authenticated as either a paired device OR a logged-in user. The existing `get_current_device` becomes one of two paths; the dependency returns the `User` (devices are owned by users — see schema change below).
- `storymaster/model/database/schema/base.py::SyncDevice` — add `user_id` FK so each device is owned by a user. Migration writes existing devices to user 1 (or fails loudly if multiple users exist — manual cleanup).
- `storymaster/main.py` — desktop stops calling `start_sync_server` on startup *only after* Phase 3. For now, keep the embedded server.

**What survives untouched**
- Desktop UI: the entire `view/` tree and `controller/common/main_page_controller.py`. Still works against local SQLite.
- `BaseModel`. Still works.
- `SyncEngine`. Still works.

**Tests**
- New: `tests/api/test_auth.py` — login/logout, password hashing, session expiry, `/api/auth/me`.
- Existing model/sync tests unaffected.

**Risks**
- The `SyncDevice → User` FK migration is the first non-trivial schema change. Do it under Alembic from day one.

---

### Phase 2 — REST CRUD surface mirroring `BaseModel` (1–2 weeks)

**Goal**: every operation the desktop currently does via `BaseModel` and via direct `Session(...)` calls in `main_page_controller.py` is reachable over HTTP. Desktop still uses local SQLite — these endpoints exist for the upcoming web frontend and for the desktop refactor in Phase 3.

**Endpoint design** (REST, not RPC):
- `GET /api/v1/storylines`, `POST`, `PUT /{id}`, `DELETE /{id}` (scoped to current user)
- `GET /api/v1/settings`, `POST`, `PUT /{id}`, `DELETE /{id}`
- `GET /api/v1/storylines/{id}/nodes` → `LitographyNode` list
- `POST /api/v1/storylines/{id}/nodes`, `PATCH /api/v1/nodes/{id}`, `DELETE /api/v1/nodes/{id}` (PATCH for position drags)
- `GET /api/v1/storylines/{id}/connections`, `POST`, `DELETE /{id}`
- `GET /api/v1/storylines/{id}/plots`, plot sections, node-to-section associations
- `GET /api/v1/settings/{id}/entities/{table_name}` — generic Lorekeeper list (uses the existing `_table_to_class_map`)
- `POST/PATCH/DELETE` on the same path
- `GET /api/v1/settings/{id}/entities` — combined entity list for Storyweaver autocomplete
- `GET /api/v1/storylines/{id}/arcs`, `/arc-types`, `/arcs/{id}/points`
- `GET /api/v1/storylines/{id}/notes` etc.
- `GET /api/v1/documents` for `.storyweaver` files (deferred to Phase 6; Phase 2 covers DB-backed entities only).

**Files to add**
- `storymaster/api/routers/storylines.py`
- `storymaster/api/routers/settings.py`
- `storymaster/api/routers/litography.py` (nodes, connections, plots, sections)
- `storymaster/api/routers/lorekeeper.py` (the generic entity router)
- `storymaster/api/routers/arcs.py`
- `storymaster/api/routers/notes.py`
- `storymaster/api/schemas/` — Pydantic models per resource. Hand-written DTOs (cleaner than auto-generation; the schema isn't huge).

**Files to modify**
- `storymaster/model/common/common_model.py` — add the few missing methods that the controller currently bypasses with raw `Session()` calls (e.g. `create_node_connection`, `delete_node_connection`, the node move that's currently inline in `NodeMixin.setup_drag_handlers`). Preparatory cleanup; doesn't break anything.

**What survives**
- Desktop unaltered.
- `BaseModel` is now a shared CRUD layer used both directly (desktop, today) and indirectly (FastAPI routes).

**Tests**
- New: `tests/api/test_crud_*.py` per router. Use FastAPI's `TestClient`.
- Existing `test_common_model.py`, `test_lorekeeper_model.py`, `test_litographer_model.py` still pass.

**Risks**
- Accidentally introducing N+1s in the JSON serialization layer. Use `joinedload` consistently as `BaseModel` already does in places like `get_character_arcs`.
- Per-user authorization checks must be on every endpoint. Centralize: a `require_storyline(storyline_id, user)` dependency that 404s if the storyline isn't the user's. Don't trust client-supplied `user_id`/`storyline_id` without verification.

---

### Phase 3 — Desktop app uses the API (2–3 weeks; biggest engineering risk on the desktop side)

**Goal**: desktop talks HTTP to the same FastAPI server the (future) web app will. Local-SQLite-only mode is gone; desktop runs its own embedded server (single user, localhost) by default and can also point at a remote one.

**Strategy**: introduce `BaseModelClient` with the same public surface as `BaseModel`. Swap at construction time.

**Files to add**
- `storymaster/model/common/base_model_client.py` — `BaseModelClient` class. Same method names as `BaseModel` (`get_litography_nodes`, `add_row`, `update_row`, `get_all_storylines`, etc.) but each calls `requests` against the API. Returns lightweight DTO objects (or dataclasses) that mimic the SQLAlchemy ORM attribute access the controller relies on (`node.id`, `node.x_position`, `node.node_type.value`). Trickiest piece — the controller does `node.node_type.name` and similar.
- `storymaster/model/common/dto.py` — dataclasses mirroring the ORM classes the controller actually reaches into.

**Files to modify**
- `storymaster/main.py` — start the embedded API server, log in as the local user automatically (a special "desktop session" flow: a token written to a config file at first run by `scripts/create_admin.py`), construct `BaseModelClient` instead of `BaseModel`.
- `storymaster/controller/common/main_page_controller.py` — replace direct `Session(self.model.engine)` blocks with new `BaseModel`/`BaseModelClient` methods. Specifically:
  - `ConnectionPoint.create_connection` (~lines 215–251): direct `Session()` → `controller.model.create_node_connection(...)`.
  - `NodeMixin.setup_drag_handlers` `mouse_release_handler` (~lines 334–357): already uses `controller.model.update_row("litography_node", ...)` — good.
  - `draw_connections` (~lines 3919–3966): direct `Session()` → `controller.model.get_node_connections(storyline_id)`.
  - Audit the rest of the controller for `Session(self.model.engine)` and refactor.

**What survives**
- All Qt UI code in `view/`. Untouched.
- The Litographer canvas drawing code, the Storyweaver editor, the Lorekeeper page. Untouched.
- Tests that go through `BaseModel` keep working when they instantiate the local `BaseModel`. Tests that exercise `BaseModelClient` need a running test server (or a mocked `requests` session — preferred).

**Tests**
- New: `tests/model/common/test_base_model_client.py` — exercises every method against a `TestClient`-driven FastAPI instance.
- Refactor controller tests so their `model` fixture can be either `BaseModel` or `BaseModelClient`. The contract surface is the same.

**Risks** *(highest engineering risk in the whole plan)*
- The controller code reaches into ORM attributes and relationship navigation in ways that are hard to fully enumerate without running it. A 4,959-line controller has surprises. Mitigation: do this phase **after** the API is locked, and keep `BaseModel` (local SQLite) selectable via env flag for fallback during the migration. Run desktop with `STORYMASTER_BACKEND=local` (today's behavior) and `STORYMASTER_BACKEND=http` (new) side-by-side until parity is proven.
- Latency: Litographer currently mutates SQL on every node drag (see `mouse_release_handler`). HTTP per release is fine; HTTP per `mouseMoveEvent` would not be. Verify position saves only fire on release (they do, but worth confirming during test).
- Sync server still embedded on desktop in this phase — double-check the desktop doesn't accidentally talk to two different DBs (its embedded API server points at the same SQLite file).

---

### Phase 4 — Web frontend foundation (2–3 weeks)

**Goal**: a React app that logs in, lists storylines and settings, and renders the **Lorekeeper** entity browser (the simplest of the three tools to port). Litographer and Storyweaver come in their own phases.

**New directory: `web/`**
```
web/
  package.json
  vite.config.ts
  src/
    main.tsx
    app.tsx
    api/client.ts        # axios/fetch wrapper, sends cookies
    api/types.ts         # generated from FastAPI OpenAPI spec
    auth/login.tsx
    layout/shell.tsx     # top nav, storyline switcher, settings switcher
    routes/
      lorekeeper/
        navigation.tsx   # mirrors LorekeeperNavigation
        entity-list.tsx
        entity-detail.tsx
    lib/queryClient.ts   # TanStack Query
```

**Stack**
- Vite + React + TypeScript
- TanStack Query for server state (matches REST-only design; no Redux needed)
- React Router for routing
- Tailwind + shadcn/ui for components
- `openapi-typescript` to codegen TS types from FastAPI's `/openapi.json`

**Files to add (Python side)**
- `storymaster/api/static.py` — mounts `web/dist` under `/` for production builds. Dev mode runs Vite separately on a different port with proxy to FastAPI.

**Lorekeeper port specifics**
- Port `entity_mappings.py` — read it server-side and expose via `GET /api/v1/lorekeeper/schema`. Frontend then knows how to render forms/sections without duplicating the data.
- The Lorekeeper UI is essentially a table-of-tables CRUD app. shadcn/ui's `Form`, `Table`, `Tabs`, `Dialog` cover everything.

**Tests**
- Frontend: Vitest + React Testing Library for components, Playwright for one or two E2E flows.
- Backend `/api/v1/lorekeeper/schema` test.

**Risks**
- FK rendering: many Lorekeeper entities have FKs (e.g. `actor.background_id` → `background`). The web form needs combobox lookups to the relevant entity table. The endpoint design must support `GET /api/v1/settings/{id}/entities/background?fields=id,name` for cheap lookups.
- The `_` table-name suffix oddity (`location_`, `object_`, `class`) needs to be normalized in URL paths or transparently mapped.

---

### Phase 5 — Litographer in React Flow (2–3 weeks; high risk)

**Goal**: the visual node canvas in the browser, fully equivalent to the Qt version.

**Why React Flow**
- Maps cleanly: `LitographyNode` rows → React Flow `Node`s (id=db id, position=`{x: x_position, y: y_position}`, type=`node_type`, data=row payload). `NodeConnection` rows → `Edge`s (id=db id, source=output_node_id, target=input_node_id).
- Built-in: pan, zoom, multi-select, minimap, drag-to-position, connection drawing from handles. Replaces all the hand-rolled `ConnectionPoint`/`AddNodeButton`/`DeleteNodeButton` code.
- Per-node-type custom components implement the shape variants (`RectangleNodeItem`, `CircleNodeItem`, `DiamondNodeItem`, `StarNodeItem`, `HexagonNodeItem`, `TriangleNodeItem`) as SVG-styled divs.

**Files to add (web)**
- `web/src/routes/litographer/canvas.tsx` — `<ReactFlow>` wrapper.
- `web/src/routes/litographer/nodes/` — one component per `NodeType` enum value, each rendering its shape.
- `web/src/routes/litographer/node-edit-panel.tsx` — replaces the right-side panel from `setup_node_editing_panel`.
- `web/src/routes/litographer/plot-section-tabs.tsx` — replaces the section tab UI.
- `web/src/routes/litographer/state.ts` — debounced position writes; on `onNodesChange`, batch position updates and PATCH every ~250ms or on drag end.

**Files to add/modify (backend)**
- Bulk endpoint: `PATCH /api/v1/storylines/{id}/nodes/positions` accepting `[{id, x, y}, ...]` so multi-node moves don't N-call.
- Stable ordering for plot sections.

**Risks**
- Connection creation flow: in Qt, connections drag from a red output dot to a green input dot. React Flow's `Handle` components do this natively, but per-node shape positioning of handles needs care for triangles and diamonds.
- The `AddNodeButton`/`DeleteNodeButton` ghost-buttons in the Qt scene don't have an obvious React Flow equivalent. Use a context menu on the canvas (right-click → add node) and a delete affordance on selected nodes — more web-conventional anyway.
- Performance: a few hundred nodes is fine; if storylines grow into thousands, virtualization becomes a concern. Defer until it bites.

---

### Phase 6 — Storyweaver in TipTap (2–3 weeks; second-highest risk)

**Goal**: the rich-text editor with entity auto-tagging, autocomplete on `[[`, hover cards, click-to-navigate, and aliases.

**Document storage strategy**
- Desktop stores docs in `.storyweaver` ZIP files (`storymaster/models/document.py`). For the webapp, store documents in the database as a new table:
  ```
  Document(id, user_id, storyline_id, setting_id, title, content_md, entity_map_json, created_at, updated_at, sync_uuid, version, deleted_at)
  ```
- Aliases live in `entity_map_json` exactly as today (compatibility with existing `.storyweaver` files for round-tripping).
- The desktop's existing ZIP file format keeps working locally (nice for portability), but uploads/imports go through `POST /api/v1/documents/import`.

**TipTap setup**
- Extensions: `StarterKit` (covers headings, bold, italic, lists, code, blockquote, hr, links), `Markdown` extension (or Tiptap's `prosemirror-markdown` bridge) so storage stays markdown.
- Custom mark: `EntityMention` with attrs `{entityId, entityType, displayText}`. Renders as a styled span. Maps to the desktop's "entity link" concept.
- Custom decoration plugin: **the auto-tag.** Mirror the desktop logic: client receives the entity-name list (from `GET /api/v1/settings/{id}/entities`), compiles per-entity regexes, runs across the doc on text changes (debounced), produces ProseMirror decorations to underline matches. **Direct port of `MarkdownHighlighter._entity_patterns`** — same algorithm, different rendering target. No `intervaltree` needed (and never was).
- Suggestion plugin (`@tiptap/suggestion`) handles the `[[` autocomplete trigger.
- Hover popup: a TipTap "FloatingMenu" or a custom tippy.js binding on entity marks. Fetches `GET /api/v1/entities/{type}/{id}` on hover.

**Files to add (web)**
- `web/src/routes/storyweaver/editor.tsx`
- `web/src/routes/storyweaver/extensions/entity-mention.ts`
- `web/src/routes/storyweaver/extensions/auto-tag-decoration.ts` — the regex-based decorator.
- `web/src/routes/storyweaver/entity-popover.tsx`
- `web/src/routes/storyweaver/document-list.tsx`

**Files to add (backend)**
- `storymaster/api/routers/documents.py` — CRUD for the new `Document` table.
- New ORM model for `Document` in `schema/base.py` + Alembic migration.
- Add `Document` to `BaseModel._table_to_class_map` and to `ENTITY_TYPE_MAP` in `sync_engine.py` (so docs sync to mobile).

**Risks** *(genuinely the highest)*
- **Regex-per-entity scaling**: the desktop already cracks under hundreds of entities (see `_print_performance_summary` in `text_editor.py` — clearly been a fight). On the web, ProseMirror decorations re-run on doc changes; debounce hard, and consider:
  - Aho-Corasick instead of N regexes (`mnemonist` package, or a small WASM build) — same input set, much faster; strict improvement over the desktop today.
  - Limit auto-tag to whole-paragraph blocks the user is editing, not the whole doc on every keystroke.
- **Markdown round-tripping**: desktop saves raw markdown text (`.storyweaver` ZIP). TipTap → markdown → DB → TipTap must be lossless for entity marks. The portable representation of `[[Entity|id]]` is documented in the desktop's editor; replicate as the canonical on-disk form.
- **Aliases**: `add_alias` mutates the document `entity_map`. Web version needs the same per-document alias state, sent up via PATCH on the document.

---

### Phase 7 — Character Arcs in React (1 week, low risk)

**Goal**: port `new_character_arcs_page.py`'s arc browser and detail page.

**Strategy**: pure CRUD over `arc_type`, `litography_arc`, `arc_point`, `arc_to_actor`, `arc_to_node`. No canvas. shadcn/ui forms + a list view. Hardest part is the linkage UI between arc points and litography nodes — a searchable picker against `GET /api/v1/storylines/{id}/nodes`.

**Files to add (web)**
- `web/src/routes/arcs/browser.tsx`
- `web/src/routes/arcs/detail.tsx`
- `web/src/routes/arcs/arc-type-manager.tsx`

---

### Phase 8 — Postgres swap + deploy hardening (1–2 weeks)

**Goal**: move from SQLite to Postgres on the shared server. Deployable.

**Backend changes**
- `storymaster/model/database/base_connection.py` reads `DATABASE_URL` env var.
- Re-run all Alembic migrations against Postgres in a staging env. Watch for SQLite-isms in the schema (very few — `BaseTable` is portable, but DDL types `Text`, `String(N)`, `Float`, `Boolean`, `DateTime(timezone=True)` are all Postgres-fine).
- Replace SQLite-backed sessions with the same `user_session` table (Postgres works fine).
- Add a `pg_dump`-based backup story replacing `BackupManager` (SQLite-file-copy only).

**Deploy**
- Single host, single uvicorn process behind nginx (TLS termination, serves `web/dist` and proxies `/api/*`).
- systemd unit for uvicorn.
- A migration runbook: "drop into staging, apply Alembic, smoke-test, swap DNS." For a handful of users, this is enough.

---

## Tests evolution

| Today | After |
|---|---|
| `tests/model/common/test_common_model.py` | Stays. Exercises local `BaseModel`. |
| `tests/model/{litographer,lorekeeper,database}/` | Stays. |
| `tests/controller/common/test_plot_management.py` | Stays. Controllers parameterize over local `BaseModel` and (Phase 3+) `BaseModelClient`. |
| `tests/controller/litographer/*` | Most stay; ones that exercise `QGraphicsScene` directly become legacy desktop-only. |
| `tests/view/*` | Mostly stay desktop-only; new web component tests added under `web/src/**/*.test.tsx`. |
| `tests/test_sync_*.py` | Stays. The sync engine doesn't change. |
| New: `tests/api/test_*.py` | FastAPI `TestClient` per router. |
| New: `tests/api/test_auth.py` | Sessions, password, login. |
| New: `tests/model/common/test_base_model_client.py` | The HTTP variant of `BaseModel`. |
| New: `web/**/*.test.tsx` | Vitest for components. |
| New: `tests/e2e/` (Playwright) | One smoke test per phase end. |

The pytest suite as a whole grows; nothing in the existing model layer needs to be deleted.

## Sync server: fold or keep separate?

**Fold.** The `/api/sync/*` and `/api/pair/*` endpoints already live in a FastAPI app — they just need to share the same auth dependency (a paired device's bearer token still works) and live next to the new CRUD routers. The mobile app keeps using the same protocol; never sees a difference. The `SyncEngine` itself doesn't change. The benefit of folding is one process, one deploy, one auth model, one OpenAPI surface.

## Risks and unknowns (consolidated)

1. **Storyweaver auto-tag at scale** — desktop already pays a real perf cost for hundreds of entities. The web port has to do better, not worse. Plan for Aho-Corasick from day one (Phase 6 risk).
2. **Litographer canvas semantics** — React Flow handles 95% out of the box; edge cases are the per-shape connection-handle positions and the section/tab interaction model. Expect a week of polish (Phase 5 risk).
3. **Controller refactor surface area** — `main_page_controller.py` is 4,959 lines and reaches into ORM internals in places. The `BaseModelClient` shim is the correct approach, but enumerating every reach-through requires running the desktop in `BackendClient` mode and fixing what breaks (Phase 3 risk).
4. **Schema migrations from "no migrations today" → Alembic** — existing `scripts/migrate_*.py` ad-hoc scripts indicate prior pain. Establishing Alembic correctly the first time matters; the schema is non-trivial (~70 tables).
5. **Per-user data scoping correctness** — a CRUD-style API that can return any storyline by id is a security risk if the auth filter isn't enforced on every endpoint. Centralized dependencies + a per-router test that "user A cannot fetch user B's row" is mandatory.
6. **Document storage divergence** — desktop = `.storyweaver` ZIP, web = `Document` table. Keep an import/export bridge so users aren't locked in.
7. **Mobile sync interaction with web edits** — conflict model is `version`-based and FK-resolved by `sync_uuid`. Web edits bump versions on the server; mobile picks them up on next pull. Just Works because the schema was already designed for it. Verify with an integration test (mobile push → web GET).
8. **Backup story** — `BackupManager` is SQLite-file-copy. Postgres needs a different approach. Easy, but don't forget it.

## Critical files for implementation

- `../storymaster/storymaster/model/common/common_model.py` — `BaseModel`. Load-bearing seam between desktop and web; the entire plan pivots on this class staying as the public CRUD surface, with `BaseModelClient` as its HTTP twin.
- `../storymaster/storymaster/controller/common/main_page_controller.py` — 4,959-line controller. All Qt-coupled UI logic and the spots that bypass `BaseModel` with direct `Session()` calls live here. Phase 3 work is concentrated here.
- `../storymaster/storymaster/model/database/schema/base.py` — schema. Phase 1 adds `User.password_hash`/`is_active`, `UserSession`, `SyncDevice.user_id`. Phase 6 adds `Document`.
- `../storymaster/storymaster/sync_server/main.py` — the existing FastAPI app, the foundation of the unified backend in Phases 1–2.
- `../storymaster/storymaster/view/storyweaver/text_editor.py` — 2,241-line Qt editor. Reference implementation for the TipTap port in Phase 6, particularly `MarkdownHighlighter` (regex-per-entity logic) and `EntityTextEditor` (suggestion/`[[` flow).

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Storymaster is a creative-writing tool (visual story plotting + database-driven world-building) that exists in two forms sharing **one backend**:

- **Desktop** — the original PySide6 app (`storymaster/view/`, `storymaster/controller/`). Still supported. Talks to local SQLite by default, or to the HTTP API when `STORYMASTER_API_URL` is set.
- **Web** — a FastAPI backend (`storymaster/api/`) + a React/Vite SPA (`web/`). The SPA is served by FastAPI's `StaticFiles` in production out of `web/dist`.

`PLAN.md` is the migration plan (desktop → web) and is the authoritative narrative of how the pieces fit; `PHASE3_TODO.md` / `PHASE6_TODO.md` track remaining work and explicitly-deferred items.

## Commands

### Backend / Python

```sh
pip install -r requirements.txt          # full env incl. dev + desktop deps
storymaster-server                        # run the API (uvicorn) — entry point storymaster.api.main:main, port 8765
python -m storymaster.api.scripts.create_admin --username alice   # create a user (no public sign-up)
alembic upgrade head                      # apply migrations (also run automatically by the Docker entrypoint)
alembic revision -m "describe change"     # new migration

pytest                                    # all tests (testpaths=tests, see pytest.ini)
pytest tests/api                          # just the web/API suite
pytest tests/api/test_storylines.py::test_name -v   # single test
STORYMASTER_TEST_PG_URL=postgresql+psycopg://user:pass@host:5432/db pytest tests/api/test_postgres.py   # Postgres integration tests (skipped without the env var)

black . && isort .                        # format (line-length 100, isort profile=black)
```

There is no Makefile; `scripts/run_tests.py` / `scripts/run_comprehensive_tests.py` are convenience wrappers but plain `pytest` is the norm.

### Frontend (`web/`)

```sh
cd web
npm install
npm run dev          # Vite dev server on :5173, proxies /api → http://127.0.0.1:8765 (set STORYMASTER_API_URL to override)
npm run build        # tsc -b --noEmit (type-check, errors fail the build) then vite build → web/dist
npm run typecheck    # tsc -b --noEmit only
npm run test         # vitest run (jsdom)
npm run test:watch
```

Path alias `@` → `web/src`.

### Docker

`docker build -t storymaster-web:latest .` builds a single image (Node stage builds the SPA, Python stage runs uvicorn). See `DOCKER.md`. The entrypoint refuses to start without `STORYMASTER_DB_URL` and runs `alembic upgrade head` first. `deploy/` holds systemd units + nginx config for a non-Docker deploy.

### Deploying

The deploy target (a Rocky Linux box) does **not** pull from a registry or build from source. The flow is **build → save → copy → `docker compose up -d`**:

1. **Dev box**: `docker build -t storymaster-web:latest .`, then `docker save storymaster-web:latest | gzip -1 > dist-deploy/storymaster-web.tar.gz` (gzip -1 is intentional — ~1.4 GB → ~340 MB, speed over ratio). Stop there — the operator does the copy + remote steps. The tarball is gitignored.
2. **Server**: `scp -r dist-deploy/ user@server:/opt/storymaster/`, then `docker load < storymaster-web.tar.gz`, fill in `.env` (`STORYMASTER_DB_URL` + `SYNC_SECRET_KEY`), `mkdir backups` (the compose bind mount uses `:Z` for SELinux relabel), `docker compose up -d`, and `docker compose exec app python -m storymaster.api.scripts.create_admin --username <name>` for the first user.
3. **Upgrade**: rebuild + save + scp the tarball; on the server `docker compose down` → `docker load < storymaster-web.tar.gz` → `docker compose up -d`. The entrypoint runs `alembic upgrade head` on every boot, so schema changes apply automatically.

`dist-deploy/` holds the operator runbook (`INSTALL.md`), the deploy-only `docker-compose.yml` (no `build:` block — references the pre-loaded `storymaster-web:latest`), `.env.example`, and the public-exposure path docs (`INTERNET.md`, `cloudflared-ingress.yml`, `truenas-nginx.conf` — Cloudflare Tunnel → TrueNAS nginx → Rocky VM:8765, firewall-restricted). The repo-root `docker-compose.yml` is the *development* variant with a `build:` block and an optional Postgres sidecar.

## Architecture

### The load-bearing seam: `BaseModel`

`storymaster/model/common/common_model.py` (`BaseModel`) is the shared data layer. It owns SQLAlchemy sessions, holds `_table_to_class_map` (table-name → ORM class), and exposes generic CRUD plus narrative-specific methods (`get_litography_nodes`, `create_character_arc`, etc.). It is used **two ways**:

1. Directly by the desktop controllers (today, against local SQLite).
2. Indirectly by the FastAPI routers (against whatever `STORYMASTER_DB_URL` points at).

`storymaster/model/common/base_model_client.py` (`BaseModelClient`) is an HTTP-speaking twin with the *same public surface*, returning dataclass DTOs (`storymaster/model/common/dto.py`) instead of ORM objects. `storymaster/main.py` picks `BaseModel` vs `BaseModelClient` based on `STORYMASTER_API_URL`. **Implication: a new data operation usually needs a `BaseModel` method first, then it's exposed via a router, then mirrored in `BaseModelClient` if the desktop needs it.**

### Schema

`storymaster/model/database/schema/base.py` (~1900 lines) — all SQLAlchemy models, all subclasses of `BaseTable`. Every row carries `sync_uuid`, `created_at`, `updated_at`, `deleted_at`, `version` (the schema is sync-ready). Domain shape:

- **Users / scoping**: `User` (has `password_hash`, `is_active` — added for web auth), `UserSession`. Per-user isolation is FK-based: `Storyline.user_id`, `Setting.user_id`; Lorekeeper entities scope under a `Setting` (`setting_id`); `Storyline`↔`Setting` is many-to-many via `StorylineToSetting`.
- **Litographer** (visual plot graph): `LitographyNode` (`NodeType` enum drives shape), `NodeConnection` (edges), `LitographyPlot` / `LitographyPlotSection` / `LitographyNodeToPlotSection`, `LitographyNotes` (`NoteType`).
- **Arcs**: `ArcType`, `LitographyArc`, `ArcPoint`.
- **Lorekeeper** (world-building): `Actor`, `Faction`, `Location`, `History`, `Object_`, `Race`, `Class_`, `Background`, `Skills`, `Stat`, etc., plus a large family of `*AOnBRelations` and `*To*` junction tables, plus `LitographyNoteTo*` link tables.
- **Documents / Storyweaver**: `Document` (HTML content, `entity_map_json`, alias map) — the web port stores rich text as HTML in the DB, unlike the desktop's `.storyweaver` ZIP files.
- **Sync**: `SyncDevice` (now has `user_id` — each device owned by a user), plus sync bookkeeping tables.

> SQLite-reserved-word table names are suffixed with `_`: `location_`, `object_`, `world_data`. The Storyweaver front-end re-maps prefixed entity ids back to these.

### Backend (`storymaster/api/`)

- `app.py` — `create_app()` builds the FastAPI app: CORS, includes all routers, then **splices in the existing `sync_server` routes** (`/api/pair/*`, `/api/sync/*`, `/api/devices/*`) — the sync server's bare `/` health check is rerouted to `/api/health` so the SPA can own `/`. The SPA static mount (`static.py`) is added **last** so its catch-all `/{path:path}` doesn't shadow API routes.
- `main.py` — uvicorn entry point (replaces the old `start_sync_server.py`). Honors `STORYMASTER_HOST` / `STORYMASTER_PORT` / `STORYMASTER_RELOAD`.
- `auth.py` — `/api/auth/login|logout|me|change-password`. Server-side sessions: opaque token in an HTTP-only cookie (`SESSION_COOKIE_NAME`), stored in `UserSession`. Argon2 hashes via `security.py` (with transparent rehash on login). Cookie is `Secure` by default — set `STORYMASTER_SECURE_COOKIES=false` for plaintext-localhost dev.
- `deps.py` — `get_current_user` dependency: tries the session cookie first, then a `Bearer` device token (so mobile sync clients keep working). `get_optional_user` is the non-raising variant.
- `authz.py` — `require_setting` (and friends): the `{setting_id}` / `{storyline_id}` URL segment **is** the authorization gate; the dependency 404s if the resource isn't owned by the current user.
- `routers/` — one module per resource: `storylines.py`, `litography.py` (nodes/connections/plots/sections), `lorekeeper.py` (a **generic** entity router driven by the `LOREKEEPER_TABLES` allowlist over `BaseModel._table_to_class_map`), `arcs.py`, `notes.py`, `storyweaver.py`, `documents.py`, `lore_packages.py`. All under `/api/v1`.
- `lore_packages.py` (module, not router) — import logic for shareable world-building packs; `scripts/opml_to_lore_pack.py` converts OPML outlines to packs; bundled packs live in `world_building_packages/`.
- `schemas/` — hand-written Pydantic DTOs per resource (deliberately not auto-generated).
- `scripts/create_admin.py` — the only way to create users.

### Frontend (`web/src/`)

- React 18 + React Router v6 + TanStack Query. `app.tsx` is the route tree; `RequireAuth` guards everything under `/` (`Shell` is the layout chrome).
- `api/client.ts` — thin `fetch` wrapper, always `credentials: "include"`, base URL from `VITE_API_URL` (empty = same-origin). `api/*.ts` are per-resource typed clients.
- `routes/litographer/` — the visual plot canvas, built on **React Flow** (`@xyflow/react`). `state.ts` is the local canvas state; `NodeType` enum values map to custom node components under `nodes/`.
- `routes/storyweaver/` — rich-text editor on **TipTap**. `extensions/entity-mention.ts` is the `[[`-trigger mention mark; `extensions/auto-tag.ts` is a direct port of the desktop's `MarkdownHighlighter` — one regex per entity name, longest-name-first, possessive-aware, whole-word — surfaced as ProseMirror decorations. Hover cards and ⌘/Ctrl-click navigation hang off `[data-entity-id]` elements.
- `routes/lorekeeper/` — generic entity list/form UI; `schema.ts` / `categories.ts` / `relationships.ts` describe the entity tables and their junction relationships to the form layer. `ImportLorePackages.tsx` is the pack-import flow.
- `routes/arcs/` — character-arc editor.
- `components/` — small in-repo primitives (Button/Card/Field/Input/Select/Textarea) styled with Tailwind; `lib/cn.ts` is the `clsx`+`tailwind-merge` helper.

### Database config & migrations

`STORYMASTER_DB_URL` (full SQLAlchemy URL, any dialect) > `STORYMASTER_DB_PATH` (SQLite file) > default `~/.local/share/storymaster/storymaster.db`. This resolution order is duplicated in `storymaster/sync_server/config.py`, `storymaster/sync_server/database.py`, and `storymaster/model/database/base_connection.py` — keep them in sync. `create_all`-on-startup is kept only for SQLite (the desktop ships without Alembic); **Postgres expects Alembic to own the schema**. `scripts/migrate_*.py` are legacy one-shot scripts predating Alembic — don't add to them; write Alembic revisions instead.

### Testing notes

- Web/API tests use shared fixtures in `tests/_web_fixtures.py` (re-exported via `tests/api/conftest.py`). Each test gets a fresh tmp SQLite **with `alembic upgrade head` run against it** — so schema-vs-migration drift fails the test suite, not the deploy. Fixtures of note: `client` (`TestClient`), `make_user`, `login_as` (returns a logged-in `TestClient`; multi-user tests get isolated clients).
- Desktop `view/` tests need a `QApplication` and are routinely skipped headless; controller tests mostly go through `BaseModel`. The `tests/test_sync_*.py` set covers the mobile sync protocol.

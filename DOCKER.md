# Storymaster — Docker deployment

Single-container deploy: one image runs the FastAPI server and serves the
SPA bundle out of `web/dist`. Postgres lives outside the image (your
existing host Postgres, or the optional sidecar in `docker-compose.yml`).

## Image overview

- **Base**: `python:3.11-slim-bookworm` (Debian) for runtime,
  `node:20-bookworm-slim` for the SPA build stage.
- **Process**: `tini` reaps zombies and forwards signals to `uvicorn`.
- **Entrypoint** (`docker-entrypoint.sh`):
  1. Refuses to start without `STORYMASTER_DB_URL` set (no silent SQLite
     fallback that would lose data on restart).
  2. Runs `alembic upgrade head` so the deployed schema always matches
     the image.
  3. `exec`s into the CMD (uvicorn).
- **User**: non-root `storymaster` (uid/gid 10001).
- **Port**: 8765.
- **Healthcheck**: `GET /api/health` every 30s (start grace 20s).
- **Image size**: ~1.4 GB. Most of that is the python:3.11 base + the
  `psycopg[binary]` wheel; size optimization via distroless or alpine is
  a deliberate non-goal for now (the deploy target is a server, not a
  fleet).

## Build

```sh
docker build -t storymaster-web:latest .
```

The build runs:
1. `npm ci` + `npm run build` in the node stage. TypeScript errors fail
   the build — same gate as CI.
2. `pip install -r requirements.txt` in the runtime stage.
3. Copies `storymaster/`, `alembic/`, `scripts/`, `web/dist/` into `/app`.

`.dockerignore` keeps tests, node_modules, virtualenvs, and the desktop
deploy artifacts out of the build context.

## Run

The minimum invocation needs a database URL:

```sh
docker run -d --name storymaster \
    -e STORYMASTER_DB_URL="postgresql+psycopg://storymaster:CHANGEME@db.example.com:5432/storymaster" \
    -p 127.0.0.1:8765:8765 \
    storymaster-web:latest
```

`-p 127.0.0.1:8765:8765` binds to localhost so a host-level reverse
proxy (nginx, Caddy, Traefik) owns TLS termination. To expose the port
publicly, drop the `127.0.0.1:` prefix — but only behind a real ACL.

### docker-compose

Copy `.env.example` to `.env`, fill in `STORYMASTER_DB_URL` and
`SYNC_SECRET_KEY`, then:

```sh
docker compose up -d
docker compose logs -f app
```

The compose file ships with the in-image Postgres sidecar **commented
out**. Uncomment its block + the `depends_on` clause if you want a
self-contained stack; pick a strong `POSTGRES_PASSWORD` and aim
`STORYMASTER_DB_URL` at hostname `postgres`.

## First-boot tasks

### Create an admin user

There's no public sign-up — admins create accounts via the CLI. From
inside the container:

```sh
docker exec -it storymaster \
    python -m storymaster.api.scripts.create_admin --username alice
```

You'll be prompted for the password. Pass `--password <p>` for scripted
setups (your shell history will see it; don't do this for real users).

### Smoke check

```sh
curl -fsS http://127.0.0.1:8765/api/health
# → {"status":"ok",...}

docker exec storymaster curl -fsS http://127.0.0.1:8765/api/health
# Same, from inside.

docker inspect --format '{{.State.Health.Status}}' storymaster
# → healthy (after the start_period)
```

## Upgrade

```sh
git pull --ff-only
docker build -t storymaster-web:latest .
docker compose up -d                # zero-downtime swap, modulo migration time
# OR for plain docker:
docker stop storymaster && docker rm storymaster
docker run ... storymaster-web:latest   # same args as the original `run`
```

The entrypoint runs `alembic upgrade head` on each container start; old
images stay valid until you swap. **Roll back** by re-running with the
prior image tag — Alembic supports `downgrade -1` for one-step rollback,
but the storyline of "ship forward" is the supported path.

## Backups

The Postgres backup script (`scripts/backup_postgres.sh`) is included in
the image. Two options:

1. **Host-side**: install postgresql-client on the host and run the
   script from cron. Cleaner for ops; no docker exec.
2. **In-container**: requires installing postgresql-client into the
   image (currently isn't, to keep size down). For the small-team
   deploy, host-side cron is the easier path.

The systemd unit + timer pair in `deploy/storymaster-backup.service` /
`.timer` work on the host without any container changes.

## Operational notes

- **Logs**: `docker logs storymaster` (or `docker compose logs app`).
  `uvicorn` writes to stdout in single-line format suitable for
  log-aggregation tools.
- **Sandboxing**: the systemd unit's strict path restrictions
  (`ProtectSystem=strict` etc.) don't transfer to the container. If
  that's a concern, run with `--read-only` and a `tmpfs` for `/tmp`.
- **Mobile sync**: paired devices reach the API at the host IP + port
  you exposed. The pairing QR-code endpoint embeds whatever the API
  reports as its local IP — for in-container use behind a reverse
  proxy, you may need to override that when serving over HTTPS.
- **Multiple workers**: the default uvicorn invocation uses one worker.
  Switch to `gunicorn -k uvicorn.workers.UvicornWorker -w N` if a single
  process becomes a bottleneck. (For the small-team scale described in
  PLAN.md, one worker is enough.)

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `STORYMASTER_DB_URL is not set` on start | Env not passed | Add `-e STORYMASTER_DB_URL=...` or set it in `.env` |
| `alembic upgrade head` errors with "could not connect" | DB unreachable from container | Check the host part of the URL; for sidecar Postgres use service name `postgres`, not `localhost` |
| Health check stuck on "starting" past 20s | Migration is running | Wait — first-boot Alembic on a new DB takes 5-30s |
| 401 on `/api/auth/me` after login | Cookie blocked | If the SPA is on a different origin from the API, set `STORYMASTER_CORS_ORIGINS` to that origin (it must be exact) and ensure the reverse proxy doesn't strip cookies |
| SPA shows a 404 on `/storyweaver` after refresh | The fallback isn't wired (shouldn't happen with this image) | `docker exec` and verify `web/dist/index.html` exists; the FastAPI catch-all serves it |

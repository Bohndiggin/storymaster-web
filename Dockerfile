# Multi-stage build: compile the SPA, then assemble a slim Python runtime.
# Build-mount caches would speed up rebuilds but require buildx; this
# Dockerfile sticks to features the legacy builder supports.

# ---------------------------------------------------------------------------
# Stage 1: SPA bundle
# ---------------------------------------------------------------------------
FROM node:20-bookworm-slim AS web-build

WORKDIR /web

# Cache npm install on a separate layer so source-only edits don't bust it.
COPY web/package.json web/package-lock.json* ./
RUN npm ci --no-audit --no-fund

# Now bring in the rest and build. tsc runs as part of `npm run build`, so
# any type errors fail the image build — that's the right shape for CI.
COPY web/ ./
RUN npm run build


# ---------------------------------------------------------------------------
# Stage 2: Python runtime
# ---------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS runtime

# Set up a non-root user. UID/GID match the systemd unit's `storymaster`
# convention so log/backup paths can be bind-mounted with consistent perms.
ARG UID=10001
ARG GID=10001
RUN groupadd --system --gid "$GID" storymaster \
 && useradd --system --uid "$UID" --gid "$GID" --no-create-home --shell /usr/sbin/nologin storymaster

# Runtime deps:
# - libpq for psycopg even though we use psycopg[binary]; harmless and
#   future-proof if anyone wants to drop the wheel.
# - curl is used by HEALTHCHECK; tini reaps zombies for sane signal handling.
RUN apt-get update \
 && apt-get install --no-install-recommends -y \
        ca-certificates \
        curl \
        tini \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps. Pinned + binary wheels keep the image rebuild fast.
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install -r requirements.txt

# App source. Order matters — copy least-changed files first.
COPY alembic.ini ./
COPY alembic ./alembic
COPY storymaster ./storymaster
COPY scripts ./scripts
COPY world_building_packages ./world_building_packages

# SPA bundle from stage 1, mounted under `web/dist` where
# storymaster.api.static.mount_static_files looks for it.
COPY --from=web-build /web/dist ./web/dist

# Entrypoint runs migrations then exec's uvicorn.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Default config for the FastAPI app. STORYMASTER_DB_URL must be supplied
# at runtime; we deliberately don't bake a default that would silently
# fall through to a SQLite file in the working directory.
ENV STORYMASTER_HOST=0.0.0.0 \
    STORYMASTER_PORT=8765 \
    PYTHONPATH=/app

USER storymaster

EXPOSE 8765

# tini gives us PID 1 → proper SIGTERM forwarding to uvicorn on docker stop.
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "storymaster.api.app:app", "--host", "0.0.0.0", "--port", "8765"]

# Liveness probe: the API exposes the health-check at /api/health (the same
# endpoint the legacy sync clients hit, just rerouted from `/`).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail --silent --show-error http://127.0.0.1:8765/api/health || exit 1

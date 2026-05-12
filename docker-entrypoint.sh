#!/bin/sh
#
# Container entrypoint for the Storymaster API.
#
# 1. Confirms `STORYMASTER_DB_URL` is set (we refuse to silently fall back
#    to SQLite-in-cwd, which would create an ephemeral DB lost on every
#    container restart).
# 2. Runs `alembic upgrade head` so the deployed image always matches
#    schema. Idempotent — no-ops when there's nothing to apply.
# 3. exec's the CMD (uvicorn) so signals reach the application directly.

set -eu

if [ -z "${STORYMASTER_DB_URL:-}" ]; then
    cat >&2 <<'EOF'
ERROR: STORYMASTER_DB_URL is not set.

Set it in your `docker run` invocation or compose file, e.g.:
    STORYMASTER_DB_URL=postgresql+psycopg://user:pass@host:5432/storymaster

Refusing to start with a default — a silent SQLite-in-cwd fallback would
lose all data on container restart.
EOF
    exit 1
fi

# `alembic` resolves the URL via env (see alembic/env.py); no extra config.
echo ">> running alembic upgrade head"
alembic upgrade head

echo ">> starting application: $*"
exec "$@"

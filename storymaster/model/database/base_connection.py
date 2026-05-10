"""Holds base connection and engine.

Used by the desktop's local SQLite path. Honors `STORYMASTER_DB_URL` /
`STORYMASTER_DB_PATH` so a single deployment can switch from SQLite to
Postgres by swapping the env, with no code changes required.

The auto-create-tables-on-startup behavior is preserved for SQLite (which
needs it because the desktop ships without Alembic on first run) but
disabled for any other dialect — Postgres deployments expect Alembic to
own the schema, and `create_all` would silently miss columns that should
have come in via migrations.
"""

import os

from sqlalchemy import Engine, create_engine


def _resolve_db_url() -> str:
    """Match the resolution order in `sync_server.config.get_database_url`.

    1. STORYMASTER_DB_URL — full SQLAlchemy URL (any dialect).
    2. STORYMASTER_DB_PATH — SQLite file path; we'll prefix it.
    3. Default user-local SQLite at ~/.local/share/storymaster/storymaster.db.
    """
    env_url = os.getenv("STORYMASTER_DB_URL")
    if env_url:
        return env_url

    env_path = os.getenv("STORYMASTER_DB_PATH")
    if env_path:
        return f"sqlite:///{env_path}"

    home_dir = os.path.expanduser("~")
    db_dir = os.path.join(home_dir, ".local", "share", "storymaster")
    os.makedirs(db_dir, exist_ok=True)
    return f"sqlite:///{os.path.join(db_dir, 'storymaster.db')}"


_db_url = _resolve_db_url()
_is_sqlite = _db_url.startswith("sqlite")

# `check_same_thread` is SQLite-specific; pass it only for SQLite URLs so
# Postgres connections aren't confused by an unknown driver kwarg.
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

# Bootstrap the SQLite file if it doesn't exist yet. For non-SQLite URLs we
# trust Alembic owns the schema and don't run `create_all` blind — it would
# create out-of-sync tables that diverge from the migration history.
if _is_sqlite:
    sqlite_path = _db_url[len("sqlite:///"):]
    if sqlite_path and not os.path.exists(sqlite_path):
        from storymaster.model.database.schema.base import BaseTable

        bootstrap_engine = create_engine(_db_url, connect_args=_connect_args)
        BaseTable.metadata.create_all(bootstrap_engine)
        bootstrap_engine.dispose()

engine = create_engine(_db_url, connect_args=_connect_args, echo=False)

# Idempotent SQLite-only schema upgrade: catches tables introduced after
# the DB was first initialized (e.g. SyncConflict, Document on existing
# desktop installs that haven't run Alembic yet). Postgres deployments
# should always be on `alembic upgrade head` instead.
if _is_sqlite:
    from storymaster.model.database.schema.base import BaseTable as _BaseTable

    _BaseTable.metadata.create_all(engine)


# Test-only engine kept for backward compatibility with anything that imports
# it. New code should use a tmp_path-backed SQLite per test (see
# tests/api/conftest.py).
_home = os.path.expanduser("~")
_test_db_path = os.path.join(_home, ".local", "share", "storymaster", "test_storymaster.db")
test_engine = create_engine(
    f"sqlite:///{_test_db_path}", connect_args={"check_same_thread": False}
)


def get_test_engine(_) -> Engine:
    """returns the test engine"""
    return test_engine

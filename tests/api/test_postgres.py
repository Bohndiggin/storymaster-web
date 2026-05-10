"""Postgres integration test.

Skipped unless `STORYMASTER_TEST_PG_URL` is set. The CI/dev workflow runs
against SQLite by default; this test exists so a deployer can point at a
disposable Postgres database and confirm:

  1. `alembic upgrade head` produces the same table set as SQLite.
  2. The cascade rules on the SQLAlchemy relationships handle a typical
     parent-delete chain (User → Storyline → Node → NodeConnection),
     which is enforced by Postgres' FK constraints (SQLite doesn't enforce
     them by default and silently lets bad cascades succeed).

Run with:

    STORYMASTER_TEST_PG_URL=postgresql+psycopg://user:pass@host:5432/db \
      pytest tests/api/test_postgres.py -v
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

PG_URL = os.getenv("STORYMASTER_TEST_PG_URL")

REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    not PG_URL,
    reason="STORYMASTER_TEST_PG_URL not set; skipping Postgres integration tests",
)


def _wipe(engine) -> None:
    """Truncate every public table except alembic_version. Lets each test
    start clean without re-running the migration."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DO $$
                DECLARE r record;
                BEGIN
                    FOR r IN SELECT tablename FROM pg_tables
                             WHERE schemaname='public' AND tablename != 'alembic_version'
                    LOOP
                        EXECUTE format('TRUNCATE TABLE %I CASCADE', r.tablename);
                    END LOOP;
                END$$;
                """
            )
        )


@pytest.fixture(scope="module")
def pg_url() -> str:
    return PG_URL  # type: ignore[return-value]


@pytest.fixture(scope="module")
def migrated_engine(pg_url):
    """Run alembic upgrade head once per session, then expose the engine."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", pg_url)
    command.upgrade(cfg, "head")

    engine = create_engine(pg_url, future=True)
    yield engine
    engine.dispose()


@pytest.fixture()
def clean_engine(migrated_engine):
    _wipe(migrated_engine)
    yield migrated_engine
    _wipe(migrated_engine)


def test_migrations_produce_expected_tables(clean_engine):
    """Smoke check: the table set on Postgres matches what we expect on
    SQLite. Catches FK syntax / type-mapping divergence early."""
    with clean_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' ORDER BY table_name"
            )
        ).all()
    tables = {r[0] for r in rows}

    # Must-haves we explicitly added in Phase 1/6 migrations.
    for required in ("user", "user_session", "sync_device", "document", "alembic_version"):
        assert required in tables, f"missing table {required!r}"

    # 70 tables on Postgres matches SQLite (verified out of band).
    assert len(tables) >= 70


def test_cascade_delete_user_removes_storylines_and_nodes(clean_engine, monkeypatch):
    """User → Storyline → LitographyNode → NodeConnection cascades on delete.

    SQLite doesn't enforce the FK constraints by default; Postgres always
    does. This is the test that would have caught the bug we fixed in
    Phase 8 — the absent `cascade="all, delete-orphan"` rules on the
    User/Storyline/Node relationships meant deleting a user used to fail
    with NotNullViolation on the child rows' FK columns.
    """
    # Point the api modules at this URL (they read from env at import).
    monkeypatch.setenv("STORYMASTER_DB_URL", PG_URL)
    # Force a re-import so SessionLocal binds to the right engine.
    import sys

    for mod in list(sys.modules):
        if mod.startswith(
            ("storymaster.api", "storymaster.sync_server.database",
             "storymaster.sync_server.main")
        ):
            del sys.modules[mod]

    from storymaster.api.app import create_app
    from storymaster.api.security import hash_password
    from storymaster.model.database.schema.base import (
        LitographyNode, NodeConnection, Storyline, User,
    )
    from storymaster.sync_server.database import SessionLocal
    from fastapi.testclient import TestClient

    username = f"pgcascade-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as s:
        s.add(User(username=username, password_hash=hash_password("hunter2"), is_active=True))
        s.commit()

    app = create_app()
    client = TestClient(app)

    r = client.post("/api/auth/login", json={"username": username, "password": "hunter2"})
    assert r.status_code == 200, r.text

    sid = client.post("/api/v1/storylines", json={"name": "S"}).json()["id"]
    n1 = client.post(
        f"/api/v1/storylines/{sid}/nodes",
        json={"name": "A", "node_type": "action"},
    ).json()["id"]
    n2 = client.post(
        f"/api/v1/storylines/{sid}/nodes",
        json={"name": "B", "node_type": "reaction"},
    ).json()["id"]
    client.post(
        f"/api/v1/storylines/{sid}/connections",
        json={"output_node_id": n1, "input_node_id": n2},
    )

    # Sanity: the rows exist before the cascade.
    with SessionLocal() as s:
        assert s.query(LitographyNode).count() == 2
        assert s.query(NodeConnection).count() == 1

    # Delete the user — should cascade through everything.
    with SessionLocal() as s:
        user = s.query(User).filter_by(username=username).one()
        s.delete(user)
        s.commit()

    with SessionLocal() as s:
        assert s.query(User).filter_by(username=username).count() == 0
        assert s.query(Storyline).filter_by(id=sid).count() == 0
        assert s.query(LitographyNode).count() == 0
        assert s.query(NodeConnection).count() == 0

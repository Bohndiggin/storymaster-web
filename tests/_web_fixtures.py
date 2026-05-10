"""Shared pytest fixtures for the web/API and BaseModelClient suites.

Imported by each conftest that needs them; not auto-discovered. Each test gets
a clean SQLite under tmp_path with Alembic migrated up — so schema-vs-migration
drift fails the test suite rather than deploy.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def db_path(tmp_path, monkeypatch) -> str:
    db_file = tmp_path / "test.db"
    url = f"sqlite:///{db_file}"
    monkeypatch.setenv("STORYMASTER_DB_URL", url)
    monkeypatch.setenv("STORYMASTER_DB_PATH", str(db_file))
    _reset_app_modules()
    _run_migrations(url)
    return str(db_file)


@pytest.fixture()
def app(db_path):
    from storymaster.api.app import create_app

    return create_app()


@pytest.fixture()
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db_session(db_path):
    from storymaster.sync_server.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def make_user(db_session):
    """Factory: create a user with a hashed password. Returns (user, plaintext)."""
    from storymaster.api.security import hash_password
    from storymaster.model.database.schema.base import User

    created: list[User] = []

    def _make(username: str = "alice", password: str = "hunter2", is_active: bool = True):
        user = User(
            username=username,
            password_hash=hash_password(password),
            is_active=is_active,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        created.append(user)
        return user, password

    return _make


@pytest.fixture()
def login_as(client, make_user):
    """Factory: create a user and return a TestClient logged in as that user.

    Each call returns a fresh isolated TestClient so multi-user tests don't
    share cookies. The first call returns the original `client` fixture
    (already wired up); subsequent calls get fresh clients on the same app.
    """
    from fastapi.testclient import TestClient

    used: list[TestClient] = []

    def _login(username: str = "alice", password: str = "hunter2"):
        user, _ = make_user(username=username, password=password)
        if not used:
            c = client
        else:
            c = TestClient(client.app)
        used.append(c)
        r = c.post("/api/auth/login", json={"username": username, "password": password})
        assert r.status_code == 200, r.text
        return c, user

    return _login


def _run_migrations(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


def _reset_app_modules() -> None:
    """Force the database/config modules to re-evaluate STORYMASTER_DB_URL.

    They cache the engine at import time, so we evict them between tests.
    """
    for mod in list(sys.modules):
        if mod.startswith(
            ("storymaster.api", "storymaster.sync_server.database",
             "storymaster.sync_server.main")
        ):
            del sys.modules[mod]

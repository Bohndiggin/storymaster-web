"""Auth flow tests: login/logout, /me, password hashing, session expiry,
bearer-token fallback. Uses an isolated SQLite per test (see conftest)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from storymaster.api.security import hash_password, verify_password
from storymaster.api.sessions import SESSION_COOKIE_NAME


def test_password_hashing_round_trip():
    h = hash_password("hunter2")
    assert h.startswith("$argon2")
    assert verify_password(h, "hunter2") is True
    assert verify_password(h, "wrong") is False


def test_login_sets_session_cookie_and_me_returns_user(client, make_user):
    user, password = make_user(username="alice", password="hunter2")

    r = client.post("/api/auth/login", json={"username": "alice", "password": password})
    assert r.status_code == 200, r.text
    assert r.json()["user"] == {"id": user.id, "username": "alice", "is_active": True}
    assert SESSION_COOKIE_NAME in r.cookies

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == {"id": user.id, "username": "alice", "is_active": True}


def test_login_wrong_password_returns_401(client, make_user):
    make_user(username="alice", password="hunter2")
    r = client.post("/api/auth/login", json={"username": "alice", "password": "nope"})
    assert r.status_code == 401
    assert SESSION_COOKIE_NAME not in r.cookies


def test_login_unknown_user_returns_401(client):
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
    assert r.status_code == 401


def test_login_inactive_user_returns_401(client, make_user):
    make_user(username="alice", password="hunter2", is_active=False)
    r = client.post("/api/auth/login", json={"username": "alice", "password": "hunter2"})
    assert r.status_code == 401


def test_me_without_session_returns_401(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_logout_revokes_session(client, make_user):
    make_user(username="alice", password="hunter2")
    client.post("/api/auth/login", json={"username": "alice", "password": "hunter2"})

    out = client.post("/api/auth/logout")
    assert out.status_code == 204

    me = client.get("/api/auth/me")
    assert me.status_code == 401


def test_expired_session_is_rejected_and_cleaned_up(client, make_user, db_session):
    from storymaster.model.database.schema.base import UserSession

    make_user(username="alice", password="hunter2")
    client.post("/api/auth/login", json={"username": "alice", "password": "hunter2"})

    # Force the existing session into the past.
    session = db_session.query(UserSession).one()
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    me = client.get("/api/auth/me")
    assert me.status_code == 401
    # Session row was deleted on detection.
    assert db_session.query(UserSession).count() == 0


def test_bearer_token_authenticates_as_device_owner(client, make_user, db_session):
    from storymaster.model.database.schema.base import SyncDevice

    user, _ = make_user(username="alice", password="hunter2")
    device = SyncDevice(
        device_id="dev-1",
        device_name="phone",
        auth_token="tok-abc",
        is_active=True,
        user_id=user.id,
    )
    db_session.add(device)
    db_session.commit()

    r = client.get("/api/auth/me", headers={"Authorization": "Bearer tok-abc"})
    assert r.status_code == 200
    assert r.json()["username"] == "alice"


def test_bearer_token_for_unowned_device_is_rejected(client, make_user, db_session):
    """Devices created before per-user ownership existed have user_id=NULL.
    They must be re-paired or backfilled — silently allowing them would
    bypass the new auth model."""
    from storymaster.model.database.schema.base import SyncDevice

    make_user(username="alice", password="hunter2")
    device = SyncDevice(
        device_id="dev-1",
        device_name="phone",
        auth_token="tok-orphan",
        is_active=True,
        user_id=None,
    )
    db_session.add(device)
    db_session.commit()

    r = client.get("/api/auth/me", headers={"Authorization": "Bearer tok-orphan"})
    assert r.status_code == 401


def test_bearer_token_unknown_returns_401(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer wat"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Change-password flow
# ---------------------------------------------------------------------------


def test_change_password_requires_auth(client):
    r = client.post(
        "/api/auth/change-password",
        json={"current_password": "x", "new_password": "yyyyyyyy"},
    )
    assert r.status_code == 401


def test_change_password_happy_path(login_as):
    client, _ = login_as("alice", password="hunter2!")
    r = client.post(
        "/api/auth/change-password",
        json={"current_password": "hunter2!", "new_password": "newpassword1"},
    )
    assert r.status_code == 204, r.text

    # Old password no longer works; new one does.
    fresh = client.post(
        "/api/auth/login", json={"username": "alice", "password": "hunter2!"}
    )
    assert fresh.status_code == 401
    fresh = client.post(
        "/api/auth/login", json={"username": "alice", "password": "newpassword1"}
    )
    assert fresh.status_code == 200


def test_change_password_wrong_current(login_as):
    client, _ = login_as("alice", password="hunter2!")
    r = client.post(
        "/api/auth/change-password",
        json={"current_password": "wrongguess", "new_password": "newpassword1"},
    )
    assert r.status_code == 400
    assert "current" in r.json()["detail"].lower()


def test_change_password_too_short(login_as):
    client, _ = login_as("alice", password="hunter2!")
    r = client.post(
        "/api/auth/change-password",
        json={"current_password": "hunter2!", "new_password": "short"},
    )
    assert r.status_code == 400


def test_change_password_must_differ(login_as):
    client, _ = login_as("alice", password="hunter2!")
    r = client.post(
        "/api/auth/change-password",
        json={"current_password": "hunter2!", "new_password": "hunter2!"},
    )
    assert r.status_code == 400


def test_change_password_revokes_other_sessions(login_as):
    """The caller's session keeps working; sessions held elsewhere die."""
    from fastapi.testclient import TestClient

    keeper, _ = login_as("alice", password="hunter2!")
    # Simulate a second browser by logging the same user in on a fresh client.
    other = TestClient(keeper.app)
    r = other.post(
        "/api/auth/login", json={"username": "alice", "password": "hunter2!"}
    )
    assert r.status_code == 200

    assert keeper.get("/api/auth/me").status_code == 200
    assert other.get("/api/auth/me").status_code == 200

    r = keeper.post(
        "/api/auth/change-password",
        json={"current_password": "hunter2!", "new_password": "newpassword1"},
    )
    assert r.status_code == 204

    # Keeper still authenticated; the other client's session was deleted.
    assert keeper.get("/api/auth/me").status_code == 200
    assert other.get("/api/auth/me").status_code == 401

"""CRUD + per-user isolation tests for /api/v1/storylines and /api/v1/settings."""

from __future__ import annotations


def test_create_and_list_storylines(login_as):
    client, user = login_as("alice")

    r = client.post("/api/v1/storylines", json={"name": "Saga", "description": "Big book"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Saga"
    assert body["user_id"] == user.id
    assert body["version"] == 1
    sid = body["id"]

    listing = client.get("/api/v1/storylines")
    assert listing.status_code == 200
    assert [s["id"] for s in listing.json()] == [sid]


def test_get_update_delete_storyline(login_as):
    client, _ = login_as("alice")
    sid = client.post("/api/v1/storylines", json={"name": "Saga"}).json()["id"]

    got = client.get(f"/api/v1/storylines/{sid}")
    assert got.status_code == 200
    assert got.json()["name"] == "Saga"

    upd = client.patch(f"/api/v1/storylines/{sid}", json={"name": "Renamed"})
    assert upd.status_code == 200
    assert upd.json()["name"] == "Renamed"
    # PATCH with no fields is allowed (no-op).
    noop = client.patch(f"/api/v1/storylines/{sid}", json={})
    assert noop.status_code == 200

    rm = client.delete(f"/api/v1/storylines/{sid}")
    assert rm.status_code == 204
    assert client.get(f"/api/v1/storylines/{sid}").status_code == 404


def test_storylines_isolated_per_user(login_as):
    alice_client, _ = login_as("alice")
    sid = alice_client.post("/api/v1/storylines", json={"name": "Alice's"}).json()["id"]

    bob_client, _ = login_as("bob")

    # Bob can't list, fetch, edit, or delete Alice's storyline.
    assert bob_client.get("/api/v1/storylines").json() == []
    assert bob_client.get(f"/api/v1/storylines/{sid}").status_code == 404
    assert bob_client.patch(f"/api/v1/storylines/{sid}", json={"name": "Stolen"}).status_code == 404
    assert bob_client.delete(f"/api/v1/storylines/{sid}").status_code == 404


def test_unauthenticated_cannot_list_storylines(client):
    assert client.get("/api/v1/storylines").status_code == 401
    assert client.post("/api/v1/storylines", json={"name": "x"}).status_code == 401


def test_create_and_list_settings(login_as):
    client, user = login_as("alice")

    r = client.post("/api/v1/settings", json={"name": "Mythic Earth"})
    assert r.status_code == 201
    sid = r.json()["id"]
    assert r.json()["user_id"] == user.id

    listing = client.get("/api/v1/settings")
    assert [s["id"] for s in listing.json()] == [sid]


def test_settings_isolated_per_user(login_as):
    alice_client, _ = login_as("alice")
    sid = alice_client.post("/api/v1/settings", json={"name": "Alice's world"}).json()["id"]

    bob_client, _ = login_as("bob")
    assert bob_client.get(f"/api/v1/settings/{sid}").status_code == 404
    assert bob_client.delete(f"/api/v1/settings/{sid}").status_code == 404


def test_link_storyline_to_setting(login_as):
    client, _ = login_as("alice")
    storyline_id = client.post("/api/v1/storylines", json={"name": "S"}).json()["id"]
    setting_id = client.post("/api/v1/settings", json={"name": "W"}).json()["id"]

    r = client.post(
        f"/api/v1/storylines/{storyline_id}/settings", json={"setting_id": setting_id}
    )
    assert r.status_code == 204

    linked = client.get(f"/api/v1/storylines/{storyline_id}/settings").json()
    assert [s["id"] for s in linked] == [setting_id]

    # Linking again is idempotent.
    again = client.post(
        f"/api/v1/storylines/{storyline_id}/settings", json={"setting_id": setting_id}
    )
    assert again.status_code == 204

    # Unlink.
    rm = client.delete(f"/api/v1/storylines/{storyline_id}/settings/{setting_id}")
    assert rm.status_code == 204
    assert client.get(f"/api/v1/storylines/{storyline_id}/settings").json() == []


def test_link_rejects_other_users_setting(login_as):
    alice_client, _ = login_as("alice")
    alice_setting_id = alice_client.post("/api/v1/settings", json={"name": "A"}).json()["id"]

    bob_client, _ = login_as("bob")
    bob_storyline_id = bob_client.post("/api/v1/storylines", json={"name": "B"}).json()["id"]

    # Bob can't reach across to link Alice's setting to his storyline.
    r = bob_client.post(
        f"/api/v1/storylines/{bob_storyline_id}/settings",
        json={"setting_id": alice_setting_id},
    )
    assert r.status_code == 404

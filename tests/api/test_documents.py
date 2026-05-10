"""Storyweaver Document CRUD tests + per-user isolation."""

from __future__ import annotations


def test_create_get_update_delete_document(login_as):
    client, user = login_as("alice")

    create = client.post(
        "/api/v1/documents",
        json={"title": "Chapter 1", "content_html": "<p>hello</p>"},
    )
    assert create.status_code == 201, create.text
    doc = create.json()
    assert doc["title"] == "Chapter 1"
    assert doc["user_id"] == user.id
    assert doc["entity_map_json"] == "{}"  # default
    did = doc["id"]

    got = client.get(f"/api/v1/documents/{did}").json()
    assert got["content_html"] == "<p>hello</p>"

    upd = client.patch(
        f"/api/v1/documents/{did}",
        json={"content_html": "<p>updated</p>", "entity_map_json": '{"actor_1":["Strider"]}'},
    )
    assert upd.status_code == 200
    assert upd.json()["content_html"] == "<p>updated</p>"
    assert upd.json()["entity_map_json"] == '{"actor_1":["Strider"]}'

    rm = client.delete(f"/api/v1/documents/{did}")
    assert rm.status_code == 204
    assert client.get(f"/api/v1/documents/{did}").status_code == 404


def test_list_documents_filters_by_storyline_and_setting(login_as):
    client, _ = login_as("alice")
    s1 = client.post("/api/v1/storylines", json={"name": "S1"}).json()["id"]
    s2 = client.post("/api/v1/storylines", json={"name": "S2"}).json()["id"]
    setting = client.post("/api/v1/settings", json={"name": "W"}).json()["id"]

    d1 = client.post(
        "/api/v1/documents",
        json={"title": "in S1", "storyline_id": s1, "setting_id": setting},
    ).json()["id"]
    d2 = client.post(
        "/api/v1/documents",
        json={"title": "in S2", "storyline_id": s2, "setting_id": setting},
    ).json()["id"]
    d3 = client.post(
        "/api/v1/documents",
        json={"title": "loose", "setting_id": setting},
    ).json()["id"]

    all_docs = client.get("/api/v1/documents").json()
    assert {d["id"] for d in all_docs} == {d1, d2, d3}

    s1_docs = client.get(f"/api/v1/documents?storyline_id={s1}").json()
    assert [d["id"] for d in s1_docs] == [d1]

    setting_docs = client.get(f"/api/v1/documents?setting_id={setting}").json()
    assert {d["id"] for d in setting_docs} == {d1, d2, d3}


def test_documents_isolated_per_user(login_as):
    alice_client, _ = login_as("alice")
    alice_doc = alice_client.post(
        "/api/v1/documents", json={"title": "Alice's"}
    ).json()["id"]

    bob_client, _ = login_as("bob")
    assert bob_client.get("/api/v1/documents").json() == []
    assert bob_client.get(f"/api/v1/documents/{alice_doc}").status_code == 404
    assert bob_client.delete(f"/api/v1/documents/{alice_doc}").status_code == 404


def test_create_rejects_other_users_storyline(login_as):
    """A user shouldn't be able to drop a doc into someone else's storyline."""
    alice_client, _ = login_as("alice")
    alice_storyline = alice_client.post(
        "/api/v1/storylines", json={"name": "private"}
    ).json()["id"]

    bob_client, _ = login_as("bob")
    r = bob_client.post(
        "/api/v1/documents",
        json={"title": "intrusion", "storyline_id": alice_storyline},
    )
    assert r.status_code == 404


def test_summary_endpoint_excludes_body(login_as):
    """The list endpoint returns summaries (no content_html), to keep the
    inbox payload small."""
    client, _ = login_as("alice")
    client.post(
        "/api/v1/documents",
        json={"title": "A", "content_html": "x" * 100_000},
    )
    listed = client.get("/api/v1/documents").json()
    assert listed and "content_html" not in listed[0]
    assert "title" in listed[0]


def test_mention_target_404s_for_other_users_entity(login_as):
    """The Storyweaver entity-detail endpoint must 404 when a logged-in user
    asks about an entity in another user's setting.

    Safety net for the editor's `[[`-trigger mention flow: even if a
    malicious payload contained a mention pointing at someone else's actor
    id, the hover/navigation lookup would never resolve, and the
    Lorekeeper detail fetch (which the ⌘-click path lands on) would 404
    too. Documents are dumb HTML blobs server-side; the entity-fetch
    endpoints are the gate.
    """
    alice_client, _ = login_as("alice")
    asid = alice_client.post("/api/v1/settings", json={"name": "W"}).json()["id"]
    actor_id = alice_client.post(
        f"/api/v1/settings/{asid}/entities/actor",
        json={"first_name": "Aragorn"},
    ).json()["id"]

    bob_client, _ = login_as("bob")
    r = bob_client.get(f"/api/v1/storyweaver/entities/actor/{actor_id}/details")
    assert r.status_code == 404
    r = bob_client.get(f"/api/v1/settings/{asid}/entities/actor/{actor_id}")
    assert r.status_code == 404


def test_document_entity_map_round_trips_aliases(login_as):
    """The alias map is opaque to the server but must survive an unmodified
    PATCH→GET round trip — the contract the editor's aliases feature
    relies on."""
    import json

    client, _ = login_as("alice")
    payload_map = {"actor_1": ["Strider"], "location_7": ["The Inn"]}
    did = client.post(
        "/api/v1/documents",
        json={"title": "T", "entity_map_json": json.dumps(payload_map)},
    ).json()["id"]

    fetched = client.get(f"/api/v1/documents/{did}").json()
    assert json.loads(fetched["entity_map_json"]) == payload_map

    new_map = {"actor_1": ["Strider", "Ranger"]}
    client.patch(
        f"/api/v1/documents/{did}",
        json={"entity_map_json": json.dumps(new_map)},
    )
    fetched = client.get(f"/api/v1/documents/{did}").json()
    assert json.loads(fetched["entity_map_json"]) == new_map

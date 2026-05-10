"""Arcs (ArcType, LitographyArc, ArcPoint) and Notes (LitographyNotes) tests."""

from __future__ import annotations


def _setup_world(client) -> dict:
    """Create the storyline + setting + arc_type + an actor used across tests."""
    storyline_id = client.post("/api/v1/storylines", json={"name": "S"}).json()["id"]
    setting_id = client.post("/api/v1/settings", json={"name": "W"}).json()["id"]
    arc_type_id = client.post(
        f"/api/v1/settings/{setting_id}/arc-types",
        json={"name": "Growth", "description": "becoming"},
    ).json()["id"]
    actor_id = client.post(
        f"/api/v1/settings/{setting_id}/entities/actor",
        json={"first_name": "Hero"},
    ).json()["id"]
    return {
        "storyline_id": storyline_id,
        "setting_id": setting_id,
        "arc_type_id": arc_type_id,
        "actor_id": actor_id,
    }


def test_arc_type_crud(login_as):
    client, _ = login_as("alice")
    sid = client.post("/api/v1/settings", json={"name": "W"}).json()["id"]

    create = client.post(
        f"/api/v1/settings/{sid}/arc-types", json={"name": "Fall", "description": "down"}
    )
    assert create.status_code == 201
    at_id = create.json()["id"]

    listing = client.get(f"/api/v1/settings/{sid}/arc-types").json()
    assert [a["id"] for a in listing] == [at_id]

    upd = client.patch(f"/api/v1/arc-types/{at_id}", json={"description": "updated"})
    assert upd.status_code == 200
    assert upd.json()["description"] == "updated"

    rm = client.delete(f"/api/v1/arc-types/{at_id}")
    assert rm.status_code == 204
    assert client.get(f"/api/v1/settings/{sid}/arc-types").json() == []


def test_arc_lifecycle_with_actor_links(login_as):
    client, _ = login_as("alice")
    ctx = _setup_world(client)

    create = client.post(
        f"/api/v1/storylines/{ctx['storyline_id']}/arcs",
        json={
            "title": "Hero rises",
            "description": "boy → king",
            "arc_type_id": ctx["arc_type_id"],
            "actor_ids": [ctx["actor_id"]],
        },
    )
    assert create.status_code == 201
    arc_id = create.json()["id"]

    detail = client.get(f"/api/v1/arcs/{arc_id}").json()
    assert detail["title"] == "Hero rises"

    upd = client.patch(
        f"/api/v1/arcs/{arc_id}", json={"title": "Hero rises (rev)", "actor_ids": []}
    )
    assert upd.status_code == 200
    assert upd.json()["title"] == "Hero rises (rev)"

    rm = client.delete(f"/api/v1/arcs/{arc_id}")
    assert rm.status_code == 204


def test_arc_rejects_arc_type_from_other_user(login_as):
    bob_client, _ = login_as("bob")
    bob_ctx = _setup_world(bob_client)

    alice_client, _ = login_as("alice")
    alice_storyline = alice_client.post("/api/v1/storylines", json={"name": "A"}).json()["id"]

    r = alice_client.post(
        f"/api/v1/storylines/{alice_storyline}/arcs",
        json={"title": "Steal", "arc_type_id": bob_ctx["arc_type_id"], "actor_ids": []},
    )
    assert r.status_code == 404


def test_arc_point_crud(login_as):
    client, _ = login_as("alice")
    ctx = _setup_world(client)
    arc_id = client.post(
        f"/api/v1/storylines/{ctx['storyline_id']}/arcs",
        json={"title": "A", "arc_type_id": ctx["arc_type_id"], "actor_ids": []},
    ).json()["id"]
    nid = client.post(
        f"/api/v1/storylines/{ctx['storyline_id']}/nodes",
        json={"name": "n", "node_type": "action"},
    ).json()["id"]

    create = client.post(
        f"/api/v1/arcs/{arc_id}/points",
        json={"title": "Point 1", "order_index": 0, "node_id": nid},
    )
    assert create.status_code == 201
    pid = create.json()["id"]

    listing = client.get(f"/api/v1/arcs/{arc_id}/points").json()
    assert [p["id"] for p in listing] == [pid]

    upd = client.patch(
        f"/api/v1/arc-points/{pid}", json={"description": "now with feeling"}
    )
    assert upd.status_code == 200
    assert upd.json()["description"] == "now with feeling"

    rm = client.delete(f"/api/v1/arc-points/{pid}")
    assert rm.status_code == 204
    assert client.get(f"/api/v1/arcs/{arc_id}/points").json() == []


def test_note_crud(login_as):
    client, _ = login_as("alice")
    sid = client.post("/api/v1/storylines", json={"name": "S"}).json()["id"]
    nid = client.post(
        f"/api/v1/storylines/{sid}/nodes",
        json={"name": "n", "node_type": "action"},
    ).json()["id"]

    create = client.post(
        f"/api/v1/storylines/{sid}/notes",
        json={
            "title": "Beat",
            "description": "what happens",
            "note_type": "what",
            "linked_node_id": nid,
        },
    )
    assert create.status_code == 201, create.text
    note_id = create.json()["id"]
    assert create.json()["note_type"] == "what"

    listing = client.get(f"/api/v1/storylines/{sid}/notes").json()
    assert [n["id"] for n in listing] == [note_id]

    upd = client.patch(
        f"/api/v1/notes/{note_id}", json={"description": "updated"}
    )
    assert upd.status_code == 200
    assert upd.json()["description"] == "updated"

    rm = client.delete(f"/api/v1/notes/{note_id}")
    assert rm.status_code == 204


def test_note_rejects_node_from_different_storyline(login_as):
    client, _ = login_as("alice")
    s1 = client.post("/api/v1/storylines", json={"name": "1"}).json()["id"]
    s2 = client.post("/api/v1/storylines", json={"name": "2"}).json()["id"]
    n_in_s2 = client.post(
        f"/api/v1/storylines/{s2}/nodes", json={"name": "x", "node_type": "action"}
    ).json()["id"]

    r = client.post(
        f"/api/v1/storylines/{s1}/notes",
        json={"title": "T", "note_type": "what", "linked_node_id": n_in_s2},
    )
    assert r.status_code == 404


def test_arcs_and_notes_isolated_per_user(login_as):
    alice_client, _ = login_as("alice")
    actx = _setup_world(alice_client)
    arc_id = alice_client.post(
        f"/api/v1/storylines/{actx['storyline_id']}/arcs",
        json={"title": "A", "arc_type_id": actx["arc_type_id"], "actor_ids": []},
    ).json()["id"]

    bob_client, _ = login_as("bob")
    assert bob_client.get(f"/api/v1/arcs/{arc_id}").status_code == 404
    assert bob_client.delete(f"/api/v1/arcs/{arc_id}").status_code == 404
    assert bob_client.get(f"/api/v1/storylines/{actx['storyline_id']}/notes").status_code == 404

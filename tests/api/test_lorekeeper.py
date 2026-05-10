"""Generic Lorekeeper CRUD: actor as the canonical entity, plus schema/index endpoints."""

from __future__ import annotations


def _new_setting(client) -> int:
    return client.post("/api/v1/settings", json={"name": "World"}).json()["id"]


def test_actor_crud_round_trip(login_as):
    client, _ = login_as("alice")
    sid = _new_setting(client)

    create = client.post(
        f"/api/v1/settings/{sid}/entities/actor",
        json={"first_name": "Aragorn", "last_name": "Elessar"},
    )
    assert create.status_code == 201, create.text
    actor = create.json()
    assert actor["first_name"] == "Aragorn"
    assert actor["setting_id"] == sid
    aid = actor["id"]

    listing = client.get(f"/api/v1/settings/{sid}/entities/actor").json()
    assert [a["id"] for a in listing] == [aid]

    detail = client.get(f"/api/v1/settings/{sid}/entities/actor/{aid}").json()
    assert detail["first_name"] == "Aragorn"

    upd = client.patch(
        f"/api/v1/settings/{sid}/entities/actor/{aid}", json={"last_name": "King"}
    ).json()
    assert upd["last_name"] == "King"

    rm = client.delete(f"/api/v1/settings/{sid}/entities/actor/{aid}")
    assert rm.status_code == 204
    assert client.get(f"/api/v1/settings/{sid}/entities/actor/{aid}").status_code == 404


def test_setting_id_in_payload_is_ignored(login_as):
    """Don't trust the client to set its own setting_id — the path wins."""
    client, _ = login_as("alice")
    sid = _new_setting(client)
    other = _new_setting(client)

    r = client.post(
        f"/api/v1/settings/{sid}/entities/actor",
        json={"first_name": "X", "setting_id": other},
    )
    assert r.status_code == 201
    assert r.json()["setting_id"] == sid


def test_unknown_table_returns_404(login_as):
    client, _ = login_as("alice")
    sid = _new_setting(client)
    r = client.get(f"/api/v1/settings/{sid}/entities/nope")
    assert r.status_code == 404


def test_litography_table_not_exposed_via_lorekeeper(login_as):
    """Tables covered by dedicated routers (litography_node, etc.) must not be
    reachable via the generic entity endpoint, even though they're in the
    table-class map."""
    client, _ = login_as("alice")
    sid = _new_setting(client)
    r = client.get(f"/api/v1/settings/{sid}/entities/litography_node")
    assert r.status_code == 404


def test_entities_isolated_per_user(login_as):
    alice_client, _ = login_as("alice")
    asid = _new_setting(alice_client)
    aid = alice_client.post(
        f"/api/v1/settings/{asid}/entities/actor",
        json={"first_name": "Aragorn"},
    ).json()["id"]

    bob_client, _ = login_as("bob")
    # Bob can't see Alice's actor, even with the right setting_id in the URL.
    assert bob_client.get(f"/api/v1/settings/{asid}/entities/actor").status_code == 404
    assert bob_client.get(f"/api/v1/settings/{asid}/entities/actor/{aid}").status_code == 404
    assert bob_client.delete(f"/api/v1/settings/{asid}/entities/actor/{aid}").status_code == 404


def test_combined_entity_index(login_as):
    client, _ = login_as("alice")
    sid = _new_setting(client)
    client.post(
        f"/api/v1/settings/{sid}/entities/actor",
        json={"first_name": "Bilbo"},
    )
    client.post(
        f"/api/v1/settings/{sid}/entities/faction", json={"name": "Shire"}
    )
    client.post(
        f"/api/v1/settings/{sid}/entities/location_", json={"name": "Hobbiton"}
    )

    index = client.get(f"/api/v1/settings/{sid}/entities").json()
    types = {e["entity_type"] for e in index}
    assert {"actor", "faction", "location_"} <= types
    names = {e["name"] for e in index}
    assert {"Bilbo", "Shire", "Hobbiton"} <= names


def test_lorekeeper_schema_lists_known_tables(login_as):
    client, _ = login_as("alice")
    body = client.get("/api/v1/lorekeeper/schema").json()
    assert "tables" in body
    assert "actor" in body["tables"]
    cols = {c["name"]: c for c in body["tables"]["actor"]["columns"]}
    assert "first_name" in cols
    assert "setting_id" in cols
    # Sanity: the FK from setting_id is exposed.
    assert cols["setting_id"]["foreign_key"]["table"] == "setting"

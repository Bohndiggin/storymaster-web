"""Litographer router tests: nodes, connections, plots, sections."""

from __future__ import annotations


def _new_storyline(client) -> int:
    return client.post("/api/v1/storylines", json={"name": "Test"}).json()["id"]


def test_node_crud_round_trip(login_as):
    client, _ = login_as("alice")
    sid = _new_storyline(client)

    create = client.post(
        f"/api/v1/storylines/{sid}/nodes",
        json={
            "name": "Inciting Incident",
            "description": "Hero leaves home",
            "node_type": "action",
            "x_position": 12.5,
            "y_position": -3.0,
        },
    )
    assert create.status_code == 201, create.text
    node = create.json()
    assert node["node_type"] == "action"
    assert node["storyline_id"] == sid
    nid = node["id"]

    listing = client.get(f"/api/v1/storylines/{sid}/nodes").json()
    assert [n["id"] for n in listing] == [nid]

    detail = client.get(f"/api/v1/nodes/{nid}").json()
    assert detail["name"] == "Inciting Incident"

    upd = client.patch(f"/api/v1/nodes/{nid}", json={"description": "Updated"}).json()
    assert upd["description"] == "Updated"
    assert upd["node_type"] == "action"  # unchanged

    rm = client.delete(f"/api/v1/nodes/{nid}")
    assert rm.status_code == 204
    assert client.get(f"/api/v1/nodes/{nid}").status_code == 404


def test_invalid_node_type_returns_422(login_as):
    client, _ = login_as("alice")
    sid = _new_storyline(client)
    r = client.post(
        f"/api/v1/storylines/{sid}/nodes",
        json={"name": "x", "node_type": "bogus"},
    )
    assert r.status_code == 422


def test_nodes_isolated_per_user(login_as):
    alice_client, _ = login_as("alice")
    asid = _new_storyline(alice_client)
    nid = alice_client.post(
        f"/api/v1/storylines/{asid}/nodes",
        json={"name": "A", "node_type": "exposition"},
    ).json()["id"]

    bob_client, _ = login_as("bob")
    assert bob_client.get(f"/api/v1/nodes/{nid}").status_code == 404
    assert bob_client.get(f"/api/v1/storylines/{asid}/nodes").status_code == 404
    assert bob_client.delete(f"/api/v1/nodes/{nid}").status_code == 404


def test_bulk_position_update(login_as):
    client, _ = login_as("alice")
    sid = _new_storyline(client)
    n1 = client.post(
        f"/api/v1/storylines/{sid}/nodes",
        json={"name": "n1", "node_type": "exposition"},
    ).json()["id"]
    n2 = client.post(
        f"/api/v1/storylines/{sid}/nodes",
        json={"name": "n2", "node_type": "exposition"},
    ).json()["id"]

    r = client.patch(
        f"/api/v1/storylines/{sid}/nodes/positions",
        json={
            "positions": [
                {"id": n1, "x": 100.0, "y": 200.0},
                {"id": n2, "x": -5.0, "y": 7.5},
            ]
        },
    )
    assert r.status_code == 204

    nodes = {n["id"]: n for n in client.get(f"/api/v1/storylines/{sid}/nodes").json()}
    assert (nodes[n1]["x_position"], nodes[n1]["y_position"]) == (100.0, 200.0)
    assert (nodes[n2]["x_position"], nodes[n2]["y_position"]) == (-5.0, 7.5)


def test_bulk_position_rejects_cross_storyline_ids(login_as):
    client, _ = login_as("alice")
    s1 = _new_storyline(client)
    s2 = _new_storyline(client)
    n_in_s2 = client.post(
        f"/api/v1/storylines/{s2}/nodes",
        json={"name": "n", "node_type": "exposition"},
    ).json()["id"]

    r = client.patch(
        f"/api/v1/storylines/{s1}/nodes/positions",
        json={"positions": [{"id": n_in_s2, "x": 1.0, "y": 1.0}]},
    )
    assert r.status_code == 404


def test_connection_crud(login_as):
    client, _ = login_as("alice")
    sid = _new_storyline(client)
    a = client.post(
        f"/api/v1/storylines/{sid}/nodes", json={"name": "A", "node_type": "action"}
    ).json()["id"]
    b = client.post(
        f"/api/v1/storylines/{sid}/nodes", json={"name": "B", "node_type": "action"}
    ).json()["id"]

    create = client.post(
        f"/api/v1/storylines/{sid}/connections",
        json={"output_node_id": a, "input_node_id": b},
    )
    assert create.status_code == 201
    cid = create.json()["id"]

    listing = client.get(f"/api/v1/storylines/{sid}/connections").json()
    assert [c["id"] for c in listing] == [cid]

    rm = client.delete(f"/api/v1/connections/{cid}")
    assert rm.status_code == 204
    assert client.get(f"/api/v1/storylines/{sid}/connections").json() == []


def test_connection_self_loop_rejected(login_as):
    client, _ = login_as("alice")
    sid = _new_storyline(client)
    a = client.post(
        f"/api/v1/storylines/{sid}/nodes", json={"name": "A", "node_type": "action"}
    ).json()["id"]

    r = client.post(
        f"/api/v1/storylines/{sid}/connections",
        json={"output_node_id": a, "input_node_id": a},
    )
    assert r.status_code == 422


def test_connection_cross_storyline_rejected(login_as):
    client, _ = login_as("alice")
    s1 = _new_storyline(client)
    s2 = _new_storyline(client)
    n1 = client.post(
        f"/api/v1/storylines/{s1}/nodes", json={"name": "x", "node_type": "action"}
    ).json()["id"]
    n2 = client.post(
        f"/api/v1/storylines/{s2}/nodes", json={"name": "y", "node_type": "action"}
    ).json()["id"]

    r = client.post(
        f"/api/v1/storylines/{s1}/connections",
        json={"output_node_id": n1, "input_node_id": n2},
    )
    assert r.status_code == 404


def test_plots_and_sections(login_as):
    client, _ = login_as("alice")
    sid = _new_storyline(client)

    pid = client.post(
        f"/api/v1/storylines/{sid}/plots",
        json={"title": "Main plot", "description": "the through-line"},
    ).json()["id"]
    assert client.get(f"/api/v1/storylines/{sid}/plots").json()[0]["id"] == pid

    section_id = client.post(
        f"/api/v1/plots/{pid}/sections",
        json={"plot_section_type": "Tension Increases"},
    ).json()["id"]
    assert client.get(f"/api/v1/plots/{pid}/sections").json()[0]["id"] == section_id

    upd = client.patch(
        f"/api/v1/plot-sections/{section_id}",
        json={"plot_section_type": "Tension Sustains"},
    )
    assert upd.status_code == 200
    assert upd.json()["plot_section_type"] == "Tension Sustains"

    # Link a node into the section.
    nid = client.post(
        f"/api/v1/storylines/{sid}/nodes",
        json={"name": "Crisis", "node_type": "twist"},
    ).json()["id"]
    link = client.post(
        f"/api/v1/plot-sections/{section_id}/nodes",
        json={"node_id": nid, "plot_section_id": section_id},
    )
    assert link.status_code == 201
    link_id = link.json()["id"]

    rm_link = client.delete(f"/api/v1/node-section-links/{link_id}")
    assert rm_link.status_code == 204

    rm_section = client.delete(f"/api/v1/plot-sections/{section_id}")
    assert rm_section.status_code == 204

    rm_plot = client.delete(f"/api/v1/plots/{pid}")
    assert rm_plot.status_code == 204
    assert client.get(f"/api/v1/storylines/{sid}/plots").json() == []


def test_plot_isolated_per_user(login_as):
    alice_client, _ = login_as("alice")
    asid = _new_storyline(alice_client)
    pid = alice_client.post(
        f"/api/v1/storylines/{asid}/plots", json={"title": "p"}
    ).json()["id"]

    bob_client, _ = login_as("bob")
    assert bob_client.delete(f"/api/v1/plots/{pid}").status_code == 404
    assert bob_client.patch(f"/api/v1/plots/{pid}", json={"title": "x"}).status_code == 404

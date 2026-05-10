"""Parity test: BaseModel and BaseModelClient must agree on observable behavior.

This is the contract a Phase-3 controller refactor relies on. If a controller
calls `controller.model.create_node_connection(a, b)` and reads
`controller.model.get_node_connections(storyline_id)`, the result shape and
semantics must be identical whether `model` is a local `BaseModel` or an HTTP
`BaseModelClient`.

We don't compare object identity or class type — only the fields the
controller actually reads (`id`, `output_node_id`, `input_node_id`, etc.).
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from storymaster.model.common.base_model_client import BaseModelClient
from storymaster.model.common.common_model import BaseModel
from storymaster.model.common.dto import LitographyNodeDTO, NodeConnectionDTO
from storymaster.model.database.schema import base as schema
from storymaster.model.database.schema.base import PlotSectionType as _PlotSectionType


@pytest.fixture()
def local_model(db_path) -> BaseModel:
    """A `BaseModel` pointed at the same migrated SQLite the API uses.

    We override BaseModel's class-level engine cache by binding the instance
    to a fresh engine for the test DB, so the local backend reads/writes the
    same rows the HTTP backend will.
    """
    from storymaster.sync_server.config import config

    url = config.get_database_url()
    engine = create_engine(url, future=True)

    with Session(engine) as session:
        user = session.query(schema.User).filter_by(username="alice").first()
        if user is None:
            user = schema.User(username="alice", is_active=True)
            session.add(user)
            session.commit()
        user_id = user.id

    m = BaseModel.__new__(BaseModel)
    m.engine = engine
    m.user_id = user_id
    return m


@pytest.fixture()
def remote_model(client, db_path, make_user) -> BaseModelClient:
    """A `BaseModelClient` logged in as the same user `local_model` uses."""
    # Reuse the user the local fixture created (or create one if local hasn't
    # run; both fixtures pick username="alice").
    from storymaster.sync_server.database import SessionLocal

    db = SessionLocal()
    try:
        user = db.query(schema.User).filter_by(username="alice").first()
        if user is None:
            from storymaster.api.security import hash_password

            user = schema.User(
                username="alice",
                password_hash=hash_password("hunter2"),
                is_active=True,
            )
            db.add(user)
            db.commit()
        else:
            from storymaster.api.security import hash_password

            user.password_hash = hash_password("hunter2")
            db.commit()
        user_id = user.id
    finally:
        db.close()

    r = client.post("/api/auth/login", json={"username": "alice", "password": "hunter2"})
    assert r.status_code == 200, r.text
    return BaseModelClient(user_id=user_id, transport=client)


def _node_view(n) -> dict:
    """Project the controller-relevant fields off either an ORM row or a DTO."""
    return {
        "id": n.id,
        "name": n.name,
        "x_position": n.x_position,
        "y_position": n.y_position,
        "node_type_value": n.node_type.value,
        "storyline_id": n.storyline_id,
    }


def _conn_view(c) -> dict:
    return {
        "id": c.id,
        "output_node_id": c.output_node_id,
        "input_node_id": c.input_node_id,
    }


def test_node_and_connection_listings_match(local_model, remote_model):
    """Build a small fixture set via the local backend, then read it back via
    both backends and verify the projection is identical."""
    storyline = remote_model.add_row("storyline", {"name": "Saga"})
    sid = storyline["id"]

    a = remote_model.add_row(
        "litography_node",
        {"name": "A", "node_type": "exposition", "x_position": 1.0, "y_position": 2.0},
        storyline_id=sid,
    )
    b = remote_model.add_row(
        "litography_node",
        {"name": "B", "node_type": "action", "x_position": 3.0, "y_position": 4.0},
        storyline_id=sid,
    )

    remote_model.create_node_connection(a["id"], b["id"])

    local_nodes = sorted(
        (_node_view(n) for n in local_model.get_litography_nodes(sid)),
        key=lambda n: n["id"],
    )
    remote_nodes = sorted(
        (_node_view(n) for n in remote_model.get_litography_nodes(sid)),
        key=lambda n: n["id"],
    )
    assert local_nodes == remote_nodes
    assert all(isinstance(n, LitographyNodeDTO) for n in remote_model.get_litography_nodes(sid))

    local_conns = sorted(
        (_conn_view(c) for c in local_model.get_node_connections(sid)),
        key=lambda c: c["id"],
    )
    remote_conns = sorted(
        (_conn_view(c) for c in remote_model.get_node_connections(sid)),
        key=lambda c: c["id"],
    )
    assert local_conns == remote_conns
    assert all(
        isinstance(c, NodeConnectionDTO) for c in remote_model.get_node_connections(sid)
    )


def test_plot_and_section_lifecycle_match(local_model, remote_model):
    """Build plots and sections through the remote backend; observe identical
    listings via the local backend (and the section/plot DTO shapes)."""
    sid = remote_model.add_row("storyline", {"name": "S"})["id"]

    plot = remote_model.create_plot(sid, "Main", "the through-line")
    assert plot.title == "Main"

    section = remote_model.create_plot_section(plot.id)
    moved = remote_model.update_plot_section_type(section.id, _PlotSectionType.RISING)
    assert moved is True

    # Local sees the same data (after fresh session).
    local_plots = local_model.get_plots_for_storyline(sid)
    assert [p.id for p in local_plots] == [plot.id]
    local_sections = local_model.get_plot_sections(plot.id)
    assert [s.id for s in local_sections] == [section.id]
    assert local_sections[0].plot_section_type == _PlotSectionType.RISING

    # Single-record fetches work via both backends.
    assert local_model.get_plot(plot.id).id == plot.id
    assert remote_model.get_plot(plot.id).id == plot.id  # type: ignore[union-attr]

    # Section delete via remote propagates.
    assert remote_model.delete_plot_section(section.id) is True
    assert local_model.get_plot_sections(plot.id) == []


def test_node_section_link_set_replaces_existing(local_model, remote_model):
    """`move_node_to_plot_section` must collapse multiple links into one."""
    sid = remote_model.add_row("storyline", {"name": "S"})["id"]
    plot = remote_model.create_plot(sid, "P")
    section_a = remote_model.create_plot_section(plot.id)
    section_b = remote_model.create_plot_section(plot.id)

    node_id = remote_model.add_row(
        "litography_node",
        {"name": "N", "node_type": "action"},
        storyline_id=sid,
    )["id"]

    remote_model.add_node_to_plot_section(node_id, section_a.id)
    remote_model.move_node_to_plot_section(node_id, section_b.id)

    # Local: only one link, pointing to section B.
    sections_a = local_model.get_nodes_in_plot_section(section_a.id, sid)
    sections_b = local_model.get_nodes_in_plot_section(section_b.id, sid)
    assert sections_a == []
    assert [n.id for n in sections_b] == [node_id]


def test_cascade_delete_node_drops_connections_and_notes(local_model, remote_model):
    """Both backends must remove a node *plus* its connections + notes.

    Critical for parity: the controller's on_delete_node path used to inline
    a multi-table delete; if the API delete didn't cascade, the desktop under
    HTTP would leave orphan FK rows.
    """
    sid = remote_model.add_row("storyline", {"name": "S"})["id"]
    a = remote_model.add_row(
        "litography_node", {"name": "A", "node_type": "action"}, storyline_id=sid
    )["id"]
    b = remote_model.add_row(
        "litography_node", {"name": "B", "node_type": "action"}, storyline_id=sid
    )["id"]
    remote_model.create_node_connection(a, b)
    remote_model.create_litography_note(
        node_id=a,
        title="Beat",
        description="...",
        note_type="what",
        storyline_id=sid,
    )

    assert remote_model.delete_node_with_associations(a, sid) is True

    # Local backend agrees the node, its connection, and its note are gone.
    assert local_model.get_node_in_storyline(a, sid) is None
    assert local_model.get_node_connections(sid) == []
    assert local_model.count_notes_for_node(a, sid) == 0


def test_lore_entities_aggregate_matches(local_model, remote_model):
    """The plural-keyed dict shape must match between backends; details
    differ (DTO dicts vs ORM rows) but the counts and ids must agree."""
    setting_id = remote_model.add_row("setting", {"name": "W"})["id"]
    remote_model.add_row(
        "actor", {"first_name": "Bilbo"}, setting_id=setting_id
    )
    remote_model.add_row("faction", {"name": "Shire"}, setting_id=setting_id)

    local = local_model.get_lore_entities_for_setting(setting_id)
    remote = remote_model.get_lore_entities_for_setting(setting_id)

    assert set(local.keys()) == set(remote.keys())
    assert {a.id for a in local["actors"]} == {a["id"] for a in remote["actors"]}
    assert {f.id for f in local["factions"]} == {f["id"] for f in remote["factions"]}


def test_note_associations_round_trip(local_model, remote_model):
    """The dispatcher map handles 11 entity types — verify it via the remote
    backend and observe identical state from the local backend."""
    setting_id = remote_model.add_row("setting", {"name": "W"})["id"]
    sid = remote_model.add_row("storyline", {"name": "S"})["id"]
    actor_id = remote_model.add_row(
        "actor", {"first_name": "Bilbo"}, setting_id=setting_id
    )["id"]
    location_id = remote_model.add_row(
        "location_", {"name": "Hobbiton"}, setting_id=setting_id
    )["id"]
    nid = remote_model.add_row(
        "litography_node", {"name": "scene", "node_type": "exposition"}, storyline_id=sid
    )["id"]
    note = remote_model.create_litography_note(
        node_id=nid,
        title="t",
        description="d",
        note_type="what",
        storyline_id=sid,
    )

    assert remote_model.create_note_association(note.id, "actor", actor_id) is True
    assert remote_model.create_note_association(note.id, "location", location_id) is True

    # Local sees the same associations via the plural-keyed dict.
    local_assocs = local_model.get_note_associations(note.id)
    remote_assocs = remote_model.get_note_associations(note.id)
    assert {a.note_id for a in local_assocs["actors"]} == {note.id}
    assert {a.actor_id for a in local_assocs["actors"]} == {actor_id}
    # Remote returns plain dicts; check keyset agrees.
    assert set(remote_assocs.keys()) == set(local_assocs.keys())
    assert [a["actor_id"] for a in remote_assocs["actors"]] == [actor_id]
    assert [a["location_id"] for a in remote_assocs["locations"]] == [location_id]

    # Delete one; both backends should observe the drop.
    assert remote_model.delete_note_association(note.id, "actor", actor_id) is True
    assert local_model.get_note_associations(note.id)["actors"] == []
    assert remote_model.get_note_associations(note.id)["actors"] == []

    # Unknown entity_type fails on both backends (the maps stay locked together).
    assert remote_model.create_note_association(note.id, "dragon", 1) is False
    assert local_model.create_note_association(note.id, "dragon", 1) is False


def test_storyweaver_search_create_details_round_trip(local_model, remote_model):
    """Storyweaver dispatchers go through `BaseModel` on both sides; the
    HTTP layer just forwards. Verify the wire format and behavior agree."""
    setting_id = remote_model.add_row("setting", {"name": "W"})["id"]

    # Create via the remote (Storyweaver "+") path.
    pid = remote_model.create_storyweaver_entity("actor", "Bilbo Baggins", setting_id)
    assert pid is not None and pid.startswith("actor_")
    actor_numeric = int(pid.split("_", 1)[1])

    # Search returns the prefix-coded payload from both backends; compare the
    # name/type fields (id format already verified).
    remote_hits = remote_model.search_storyweaver_entities(setting_id)
    local_hits = local_model.search_storyweaver_entities(setting_id)

    def _trimmed(hits):
        return sorted(((h["type"], h["name"], h["id"]) for h in hits))

    assert _trimmed(remote_hits) == _trimmed(local_hits)

    # Filter case is also identical.
    assert (
        _trimmed(remote_model.search_storyweaver_entities(setting_id, "Bilbo"))
        == _trimmed(local_model.search_storyweaver_entities(setting_id, "Bilbo"))
    )

    # Hover details match exactly.
    remote_details = remote_model.get_storyweaver_entity_details("actor", actor_numeric)
    local_details = local_model.get_storyweaver_entity_details("actor", actor_numeric)
    assert remote_details == local_details
    assert remote_details is not None
    assert remote_details[0] == "Bilbo Baggins"

    # Unknown type returns None on both sides.
    assert remote_model.get_storyweaver_entity_details("dragon", 1) is None
    assert local_model.get_storyweaver_entity_details("dragon", 1) is None

    # Create with unknown type returns None on both sides.
    assert remote_model.create_storyweaver_entity("dragon", "x", setting_id) is None
    assert local_model.create_storyweaver_entity("dragon", "x", setting_id) is None


def test_storyweaver_details_404s_for_other_users_entity(login_as):
    """An attacker with a valid session must not be able to fetch details for
    an entity in another user's setting, even by guessing the (type, id) pair."""
    alice_client, _ = login_as("alice")
    asid = alice_client.post("/api/v1/settings", json={"name": "W"}).json()["id"]
    actor_id = alice_client.post(
        f"/api/v1/settings/{asid}/entities/actor",
        json={"first_name": "Aragorn"},
    ).json()["id"]

    bob_client, _ = login_as("bob")
    r = bob_client.get(f"/api/v1/storyweaver/entities/actor/{actor_id}/details")
    assert r.status_code == 404


def test_litography_notes_round_trip_through_remote(local_model, remote_model):
    """create_litography_note + update + delete via remote, observed locally."""
    sid = remote_model.add_row("storyline", {"name": "S"})["id"]
    nid = remote_model.add_row(
        "litography_node", {"name": "n", "node_type": "action"}, storyline_id=sid
    )["id"]

    note = remote_model.create_litography_note(
        node_id=nid,
        title="Beat",
        description="initial",
        note_type="what",
        storyline_id=sid,
    )
    assert note.title == "Beat"

    assert remote_model.update_litography_note(
        note.id, sid, description="revised"
    ) is True

    local_notes = local_model.get_notes_for_node(nid, sid)
    assert [n.description for n in local_notes] == ["revised"]

    assert remote_model.delete_litography_note(note.id, sid) is True
    assert local_model.count_notes_for_node(nid, sid) == 0


def test_storyline_setting_derivation_matches(local_model, remote_model):
    """The controller's storyline-switch path needs the linked-setting id;
    both backends must agree on that one number for the same input."""
    sid = remote_model.add_row("storyline", {"name": "S"})["id"]
    setting_id = remote_model.add_row("setting", {"name": "W"})["id"]
    remote_model.link_storyline_to_setting(sid, setting_id)

    assert remote_model.get_first_setting_id_for_storyline(sid) == setting_id
    assert local_model.get_first_setting_id_for_storyline(sid) == setting_id

    assert remote_model.get_first_storyline_id_for_setting(setting_id) == sid
    assert local_model.get_first_storyline_id_for_setting(setting_id) == sid

    # Empty cases also agree.
    other_sid = remote_model.add_row("storyline", {"name": "Other"})["id"]
    assert remote_model.get_first_setting_id_for_storyline(other_sid) is None
    assert local_model.get_first_setting_id_for_storyline(other_sid) is None


def test_input_output_connections_split(local_model, remote_model):
    sid = remote_model.add_row("storyline", {"name": "S"})["id"]
    a = remote_model.add_row(
        "litography_node", {"name": "A", "node_type": "action"}, storyline_id=sid
    )["id"]
    b = remote_model.add_row(
        "litography_node", {"name": "B", "node_type": "action"}, storyline_id=sid
    )["id"]
    remote_model.create_node_connection(a, b)

    # `a` has one outgoing, no incoming.
    assert remote_model.get_input_connections_for_node(a) == []
    assert len(remote_model.get_output_connections_for_node(a)) == 1
    # `b` has one incoming, no outgoing.
    assert len(remote_model.get_input_connections_for_node(b)) == 1
    assert remote_model.get_output_connections_for_node(b) == []

    # Local backend agrees.
    assert local_model.get_input_connections_for_node(a) == []
    assert len(local_model.get_output_connections_for_node(a)) == 1
    assert len(local_model.get_input_connections_for_node(b)) == 1
    assert local_model.get_output_connections_for_node(b) == []


def test_create_node_connection_is_idempotent_under_both(local_model, remote_model):
    """Both backends must collapse a duplicate (output→input) into the same row."""
    sid = remote_model.add_row("storyline", {"name": "S"})["id"]
    a = remote_model.add_row(
        "litography_node", {"name": "A", "node_type": "action"}, storyline_id=sid
    )
    b = remote_model.add_row(
        "litography_node", {"name": "B", "node_type": "action"}, storyline_id=sid
    )

    first_local = local_model.create_node_connection(a["id"], b["id"])
    second_local = local_model.create_node_connection(a["id"], b["id"])
    assert first_local.id == second_local.id

    first_remote = remote_model.create_node_connection(a["id"], b["id"])
    second_remote = remote_model.create_node_connection(a["id"], b["id"])
    assert first_remote.id == second_remote.id
    # Both backends saw the same single row (no duplicates created).
    assert (
        len(local_model.get_node_connections(sid))
        == len(remote_model.get_node_connections(sid))
        == 1
    )

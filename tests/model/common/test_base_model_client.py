"""BaseModelClient tests against the live FastAPI app via TestClient.

This is the contract test for the BaseModel ↔ BaseModelClient seam: any
controller path that works against a local BaseModel must work identically
against a BaseModelClient when both wrap the same logical user.
"""

from __future__ import annotations

import pytest

from storymaster.model.common.base_model_client import BaseModelClient
from storymaster.model.common.dto import (
    LitographyNodeDTO,
    NodeConnectionDTO,
    SettingDTO,
    StorylineDTO,
)
from storymaster.model.database.schema.base import NodeType


@pytest.fixture()
def authed_client(client, make_user):
    user, password = make_user(username="alice", password="hunter2")
    r = client.post("/api/auth/login", json={"username": user.username, "password": password})
    assert r.status_code == 200, r.text
    return client, user


@pytest.fixture()
def model_client(authed_client) -> BaseModelClient:
    transport, user = authed_client
    return BaseModelClient(user_id=user.id, transport=transport)


# ---------------------------------------------------------------------------
# Storyline / Setting
# ---------------------------------------------------------------------------


def test_storylines_round_trip(model_client: BaseModelClient):
    assert model_client.get_all_storylines() == []

    created = model_client.add_row(
        "storyline", {"name": "Saga", "description": "Big book"}
    )
    sid = created["id"]

    listing = model_client.get_all_storylines()
    assert len(listing) == 1
    assert isinstance(listing[0], StorylineDTO)
    assert listing[0].name == "Saga"

    one = model_client.get_storyline_by_id(sid)
    assert one is not None
    assert one.id == sid
    assert one.user_id == model_client.user_id

    assert model_client.update_storyline(sid, name="Renamed") is True
    assert model_client.get_storyline_by_id(sid).name == "Renamed"  # type: ignore[union-attr]

    assert model_client.delete_storyline(sid) is True
    assert model_client.get_storyline_by_id(sid) is None


def test_settings_round_trip(model_client: BaseModelClient):
    setting = model_client.add_row("setting", {"name": "World"})
    s = model_client.get_setting_by_id(setting["id"])
    assert isinstance(s, SettingDTO)
    assert s.name == "World"


def test_link_storyline_to_setting(model_client: BaseModelClient):
    storyline_id = model_client.add_row("storyline", {"name": "S"})["id"]
    setting_id = model_client.add_row("setting", {"name": "W"})["id"]

    assert model_client.link_storyline_to_setting(storyline_id, setting_id) is True
    linked = model_client.get_settings_for_storyline(storyline_id)
    assert [s.id for s in linked] == [setting_id]

    assert model_client.unlink_storyline_from_setting(storyline_id, setting_id) is True
    assert model_client.get_settings_for_storyline(storyline_id) == []


# ---------------------------------------------------------------------------
# Litographer
# ---------------------------------------------------------------------------


def test_node_create_list_and_dto_shape(model_client: BaseModelClient):
    sid = model_client.add_row("storyline", {"name": "S"})["id"]
    raw = model_client.add_row(
        "litography_node",
        {"name": "Inciting", "node_type": "action", "x_position": 10.0, "y_position": -5.0},
        storyline_id=sid,
    )
    nid = raw["id"]

    nodes = model_client.get_litography_nodes(sid)
    assert len(nodes) == 1
    n = nodes[0]
    assert isinstance(n, LitographyNodeDTO)
    assert n.id == nid
    assert n.x_position == 10.0
    assert n.y_position == -5.0
    # Critical: the controller does node.node_type.value — so node_type must
    # be a real Enum instance, not a string.
    assert n.node_type is NodeType.ACTION
    assert n.node_type.value == "action"


def test_update_node_via_update_row(model_client: BaseModelClient):
    sid = model_client.add_row("storyline", {"name": "S"})["id"]
    nid = model_client.add_row(
        "litography_node",
        {"name": "n", "node_type": "exposition"},
        storyline_id=sid,
    )["id"]

    model_client.update_row(
        "litography_node", {"id": nid, "x_position": 99.0, "y_position": -3.0}
    )
    refreshed = model_client.get_row_by_id("litography_node", nid)
    assert refreshed is not None
    assert refreshed["x_position"] == 99.0


def test_node_connection_round_trip(model_client: BaseModelClient):
    sid = model_client.add_row("storyline", {"name": "S"})["id"]
    a = model_client.add_row(
        "litography_node",
        {"name": "A", "node_type": "action"},
        storyline_id=sid,
    )["id"]
    b = model_client.add_row(
        "litography_node",
        {"name": "B", "node_type": "action"},
        storyline_id=sid,
    )["id"]

    assert model_client.get_node_connections(sid) == []

    conn = model_client.create_node_connection(a, b)
    assert isinstance(conn, NodeConnectionDTO)
    assert conn.output_node_id == a
    assert conn.input_node_id == b

    listing = model_client.get_node_connections(sid)
    assert [c.id for c in listing] == [conn.id]

    assert model_client.delete_node_connection(conn.id) is True  # type: ignore[arg-type]
    assert model_client.get_node_connections(sid) == []


# ---------------------------------------------------------------------------
# Lorekeeper (generic table dispatch)
# ---------------------------------------------------------------------------


def test_lorekeeper_actor_via_add_row(model_client: BaseModelClient):
    setting_id = model_client.add_row("setting", {"name": "W"})["id"]
    actor = model_client.add_row(
        "actor", {"first_name": "Aragorn"}, setting_id=setting_id
    )
    aid = actor["id"]

    rows = model_client.get_all_rows_as_dicts("actor", setting_id=setting_id)
    assert [r["id"] for r in rows] == [aid]

    model_client.current_setting_id = setting_id
    fetched = model_client.get_row_by_id("actor", aid)
    assert fetched is not None
    assert fetched["first_name"] == "Aragorn"

    model_client.update_row(
        "actor", {"id": aid, "last_name": "Elessar", "setting_id": setting_id}
    )
    refreshed = model_client.get_row_by_id("actor", aid)
    assert refreshed is not None
    assert refreshed["last_name"] == "Elessar"


def test_get_table_data_returns_headers_and_tuples(model_client: BaseModelClient):
    setting_id = model_client.add_row("setting", {"name": "W"})["id"]
    model_client.add_row("faction", {"name": "Shire"}, setting_id=setting_id)

    headers, rows = model_client.get_table_data("faction", setting_id=setting_id)
    assert "name" in headers
    name_idx = headers.index("name")
    assert rows[0][name_idx] == "Shire"


# ---------------------------------------------------------------------------
# Auth boundary
# ---------------------------------------------------------------------------


def test_engine_property_raises(model_client: BaseModelClient):
    """Direct `Session(self.model.engine)` paths must fail loudly under HTTP."""
    with pytest.raises(RuntimeError) as exc:
        _ = model_client.engine
    assert "BaseModelClient" in str(exc.value)


def test_unknown_table_raises_not_implemented(model_client: BaseModelClient):
    with pytest.raises(NotImplementedError):
        model_client.add_row("not_a_real_table", {"x": 1})


def test_get_current_user(model_client: BaseModelClient):
    me = model_client.get_current_user()
    assert me is not None
    assert me.username == "alice"
    assert me.id == model_client.user_id


def test_create_user_raises_not_implemented(model_client: BaseModelClient):
    with pytest.raises(NotImplementedError):
        model_client.create_user("bob")

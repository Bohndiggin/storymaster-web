"""Storyweaver entity dispatchers on BaseModel.

These power the Storyweaver editor's autocomplete / "+ create" / hover-card
flows. The HTTP backend doesn't expose them yet (NotImplementedError), so this
test only covers the local backend — the parity story for the remote backend
is tracked in PHASE3_TODO.md.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from storymaster.model.common.common_model import BaseModel
from storymaster.model.database.schema import base as schema


@pytest.fixture()
def model() -> BaseModel:
    engine = create_engine("sqlite:///:memory:", future=True)
    schema.BaseTable.metadata.create_all(engine)
    with Session(engine) as session:
        user = schema.User(username="alice")
        session.add(user)
        session.flush()
        setting = schema.Setting(name="W", user_id=user.id)
        session.add(setting)
        session.commit()
        sid = setting.id
    m = BaseModel.__new__(BaseModel)
    m.engine = engine
    m.user_id = 1
    m._setting_id = sid  # for the test
    return m


def test_search_returns_prefix_coded_ids_and_sorts_alphabetically(model: BaseModel):
    sid = model._setting_id  # type: ignore[attr-defined]

    actor = model.add_row(
        "actor", {"first_name": "Bilbo", "last_name": "Baggins"}, setting_id=sid
    )
    model.add_row("location_", {"name": "The Shire"}, setting_id=sid)
    model.add_row("faction", {"name": "Aragorn's Company"}, setting_id=sid)

    results = model.search_storyweaver_entities(sid)
    names = [r["name"] for r in results]
    # Sorted case-insensitively.
    assert names == sorted(names, key=str.lower)
    # Prefix-coded ids.
    types_seen = {r["type"] for r in results}
    assert {"actor", "location", "faction"} <= types_seen
    actor_entry = next(r for r in results if r["type"] == "actor")
    assert actor_entry["id"].startswith("actor_")
    assert actor_entry["name"] == "Bilbo Baggins"


def test_search_with_query_filters_substring(model: BaseModel):
    sid = model._setting_id  # type: ignore[attr-defined]
    model.add_row("actor", {"first_name": "Aragorn"}, setting_id=sid)
    model.add_row("actor", {"first_name": "Gimli"}, setting_id=sid)

    hits = model.search_storyweaver_entities(sid, query="Ara")
    assert [h["name"] for h in hits] == ["Aragorn"]


def test_create_actor_splits_first_and_last_name(model: BaseModel):
    sid = model._setting_id  # type: ignore[attr-defined]

    pid = model.create_storyweaver_entity("actor", "Frodo Baggins", sid)
    assert pid is not None and pid.startswith("actor_")
    actor_id = int(pid.split("_", 1)[1])

    row = model.get_row_by_id("actor", actor_id)
    assert row is not None
    assert row["first_name"] == "Frodo"
    assert row["last_name"] == "Baggins"


def test_create_actor_single_name_goes_to_first_name(model: BaseModel):
    sid = model._setting_id  # type: ignore[attr-defined]
    pid = model.create_storyweaver_entity("actor", "Sauron", sid)
    actor_id = int(pid.split("_", 1)[1])
    row = model.get_row_by_id("actor", actor_id)
    assert row["first_name"] == "Sauron"
    assert row["last_name"] == ""


def test_create_simple_entity(model: BaseModel):
    sid = model._setting_id  # type: ignore[attr-defined]

    for kind, table in (
        ("location", "location_"),
        ("faction", "faction"),
        ("object", "object_"),
        ("worlddata", "world_data"),
    ):
        pid = model.create_storyweaver_entity(kind, f"Test {kind}", sid)
        assert pid is not None and pid.startswith(f"{kind}_")
        # The row exists in the storage table.
        rid = int(pid.split("_", 1)[1])
        assert model.get_row_by_id(table, rid) is not None


def test_create_unknown_type_returns_none(model: BaseModel):
    sid = model._setting_id  # type: ignore[attr-defined]
    assert model.create_storyweaver_entity("ufo", "name", sid) is None


def test_get_actor_details(model: BaseModel):
    sid = model._setting_id  # type: ignore[attr-defined]
    pid = model.create_storyweaver_entity("actor", "Gandalf the Gray", sid)
    aid = int(pid.split("_", 1)[1])
    # Augment the row so the detail builder has something to format.
    model.update_row(
        "actor",
        {
            "id": aid,
            "title": "Wizard",
            "actor_role": "Mentor",
            "actor_age": 2000,
            "job": "Itinerant",
        },
    )

    name, details = model.get_storyweaver_entity_details("actor", aid)
    assert name == "Gandalf the Gray"
    # All four detail lines present, in the expected order.
    assert "Title: Wizard" in details
    assert "Role: Mentor" in details
    assert "Age: 2000" in details
    assert "Occupation: Itinerant" in details

    # Backwards-compat alias: "character" works too.
    name2, _ = model.get_storyweaver_entity_details("character", aid)
    assert name2 == name


def test_get_details_unknown_type_returns_none(model: BaseModel):
    assert model.get_storyweaver_entity_details("dragon", 1) is None


def test_get_details_missing_id_returns_none(model: BaseModel):
    assert model.get_storyweaver_entity_details("actor", 9999) is None

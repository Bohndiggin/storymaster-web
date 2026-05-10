"""Targeted tests for BaseModel's node-connection methods.

These were added in Phase 2 to give the Litographer controller somewhere to
delegate instead of calling `Session(self.model.engine)` inline. The tests
exercise them against an in-memory SQLite so we don't depend on the
filesystem-backed default engine.
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
        user = schema.User(username="alice", is_active=True)
        session.add(user)
        session.flush()
        storyline = schema.Storyline(name="S", user_id=user.id)
        session.add(storyline)
        session.flush()
        a = schema.LitographyNode(
            name="A",
            node_type=schema.NodeType.ACTION,
            storyline_id=storyline.id,
        )
        b = schema.LitographyNode(
            name="B",
            node_type=schema.NodeType.ACTION,
            storyline_id=storyline.id,
        )
        session.add_all([a, b])
        session.commit()
        storyline_id = storyline.id
        a_id = a.id
        b_id = b.id

    m = BaseModel.__new__(BaseModel)
    m.engine = engine
    m.user_id = 1
    m._storyline_id = storyline_id  # for the test to read back
    m._a_id = a_id
    m._b_id = b_id
    return m


def test_create_get_delete_node_connection(model: BaseModel):
    storyline_id = model._storyline_id  # type: ignore[attr-defined]
    a_id = model._a_id  # type: ignore[attr-defined]
    b_id = model._b_id  # type: ignore[attr-defined]

    assert model.get_node_connections(storyline_id) == []

    connection = model.create_node_connection(a_id, b_id)
    assert connection.id is not None
    assert connection.output_node_id == a_id
    assert connection.input_node_id == b_id

    fetched = model.get_node_connections(storyline_id)
    assert [c.id for c in fetched] == [connection.id]

    # Idempotent: second call with the same pair returns the existing row.
    again = model.create_node_connection(a_id, b_id)
    assert again.id == connection.id

    assert model.delete_node_connection(connection.id) is True
    assert model.delete_node_connection(connection.id) is False
    assert model.get_node_connections(storyline_id) == []


def test_get_node_connections_filters_by_storyline(model: BaseModel):
    """A connection in storyline X must not appear when querying storyline Y."""
    storyline_id = model._storyline_id  # type: ignore[attr-defined]
    a_id = model._a_id  # type: ignore[attr-defined]
    b_id = model._b_id  # type: ignore[attr-defined]
    model.create_node_connection(a_id, b_id)

    # Build a second storyline with its own nodes; its connection list must be empty.
    with Session(model.engine) as session:
        other = schema.Storyline(name="other", user_id=1)
        session.add(other)
        session.commit()
        other_id = other.id

    assert [c.id for c in model.get_node_connections(storyline_id)] != []
    assert model.get_node_connections(other_id) == []

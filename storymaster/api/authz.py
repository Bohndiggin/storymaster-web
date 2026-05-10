"""Per-resource authorization helpers.

These return 404 (not 403) when a user requests something that isn't theirs —
the API must not let one user probe for another user's row IDs.

Storyline and Setting are user-owned directly. Everything else (nodes,
connections, plots, arcs, notes, lorekeeper entities) authorizes by walking up
to the owning Storyline or Setting.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from storymaster.api.deps import get_current_user
from storymaster.model.database.schema import base as schema
from storymaster.sync_server.database import get_db


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found")


def require_storyline(
    storyline_id: int,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.Storyline:
    storyline = db.get(schema.Storyline, storyline_id)
    if storyline is None or storyline.user_id != user.id:
        raise _not_found("Storyline")
    return storyline


def require_setting(
    setting_id: int,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.Setting:
    setting = db.get(schema.Setting, setting_id)
    if setting is None or setting.user_id != user.id:
        raise _not_found("Setting")
    return setting


def require_node(
    node_id: int,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.LitographyNode:
    node = db.get(schema.LitographyNode, node_id)
    if node is None or node.storyline is None or node.storyline.user_id != user.id:
        raise _not_found("Node")
    return node


def require_plot(
    plot_id: int,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.LitographyPlot:
    plot = db.get(schema.LitographyPlot, plot_id)
    if plot is None or plot.storyline is None or plot.storyline.user_id != user.id:
        raise _not_found("Plot")
    return plot


def require_arc(
    arc_id: int,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.LitographyArc:
    arc = db.get(schema.LitographyArc, arc_id)
    if arc is None or arc.storyline is None or arc.storyline.user_id != user.id:
        raise _not_found("Arc")
    return arc


def require_note(
    note_id: int,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.LitographyNotes:
    note = db.get(schema.LitographyNotes, note_id)
    if note is None or note.storyline is None or note.storyline.user_id != user.id:
        raise _not_found("Note")
    return note


def assert_node_in_storyline(node: schema.LitographyNode, storyline_id: int) -> None:
    if node.storyline_id != storyline_id:
        raise _not_found("Node")


def get_storyline_owned_node(
    db: Session, user: schema.User, node_id: int
) -> schema.LitographyNode:
    """Look up a node and confirm the requesting user owns its storyline.

    Returns the node or raises 404. Used by handlers that take node IDs in the
    request body (rather than the path), so they need to authorize each one.
    """
    node = db.get(schema.LitographyNode, node_id)
    if node is None or node.storyline is None or node.storyline.user_id != user.id:
        raise _not_found("Node")
    return node

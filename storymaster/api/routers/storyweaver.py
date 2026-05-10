"""Storyweaver-flavored entity endpoints.

The Storyweaver editor (and its desktop equivalent) doesn't want raw rows from
six different tables — it wants a single typed list with prefix-coded ids
(`actor_42`, `location_7`, ...) and a hover-card detail string. These are the
endpoints behind those flows; they delegate to the same `BaseModel` helpers
the local desktop uses, so the wire format and the in-process API can't
drift.

Authorization:
- `search` and `create` ride on the path's `setting_id` → `require_setting`.
- `details` looks up the entity row and verifies the requesting user owns
  its setting before returning anything (so an attacker can't probe ids by
  type, even with a valid session).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel as _PydanticBase
from sqlalchemy.orm import Session

from storymaster.api.authz import require_setting
from storymaster.api.deps import get_current_user
from storymaster.model.common.common_model import BaseModel as _BaseModel
from storymaster.model.database.schema import base as schema
from storymaster.sync_server.database import get_db

router = APIRouter(prefix="/api/v1", tags=["storyweaver"])


# Type → ORM class for the `details` ownership check. "character" is an alias
# for "actor" the desktop kept around for backward compat; we mirror it here.
_DETAIL_OWNER_LOOKUP: dict[str, type] = {
    "actor": schema.Actor,
    "character": schema.Actor,
    "location": schema.Location,
    "faction": schema.Faction,
    "object": schema.Object_,
    "worlddata": schema.WorldData,
}


class StoryweaverEntityCreate(_PydanticBase):
    entity_type: str
    entity_name: str


@router.get("/settings/{setting_id}/storyweaver/entities")
def search_entities(
    q: str | None = Query(default=None, description="Substring filter; omit for full list."),
    setting: schema.Setting = Depends(require_setting),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Cross-table substring search. Returns the same prefix-coded payload
    BaseModel.search_storyweaver_entities produces, so the desktop's existing
    handler doesn't change shape between local and HTTP backends."""
    return _model_bound_to(db, setting.user_id).search_storyweaver_entities(
        setting.id, q if q else None
    )


@router.post(
    "/settings/{setting_id}/storyweaver/entities",
    status_code=status.HTTP_201_CREATED,
)
def create_entity(
    payload: StoryweaverEntityCreate,
    setting: schema.Setting = Depends(require_setting),
    db: Session = Depends(get_db),
) -> dict:
    """Create from the editor's "+ entity" affordance.

    Returns `{"id": "<prefix>_<numeric>"}`; 422 if `entity_type` isn't one
    we know how to dispatch."""
    new_id = _model_bound_to(db, setting.user_id).create_storyweaver_entity(
        payload.entity_type, payload.entity_name, setting.id
    )
    if new_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported entity_type: {payload.entity_type!r}",
        )
    return {"id": new_id}


@router.get("/storyweaver/entities/{entity_type}/{entity_id}/details")
def get_entity_details(
    entity_type: str,
    entity_id: int,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Hover-card payload: `{name, details}`. 404 if the entity is missing or
    the requesting user doesn't own the setting it lives in."""
    cls = _DETAIL_OWNER_LOOKUP.get(entity_type)
    if cls is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown entity type"
        )
    row = db.get(cls, entity_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    setting = db.get(schema.Setting, row.setting_id)
    if setting is None or setting.user_id != user.id:
        # Don't reveal that the row exists for someone else.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    result = _model_bound_to(db, user.id).get_storyweaver_entity_details(
        entity_type, entity_id
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    name, details = result
    return {"name": name, "details": details}


def _model_bound_to(db: Session, user_id: int) -> _BaseModel:
    """Build a BaseModel pinned to the request's engine.

    Reusing BaseModel's helpers from a request handler is a deliberate seam:
    one source of truth for the entity formatting logic, two transports
    (local + HTTP) consuming it.
    """
    model = _BaseModel.__new__(_BaseModel)
    model.engine = db.get_bind()
    model.user_id = user_id
    return model

"""Character arcs: ArcType (per setting) and LitographyArc + ArcPoint (per storyline).

Actor links are managed via the `actor_ids` array on create/update — that
matches `BaseModel.create_character_arc/update_character_arc` semantics so the
desktop refactor in Phase 3 stays a thin shim.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from storymaster.api.authz import require_arc, require_setting, require_storyline
from storymaster.api.deps import get_current_user
from storymaster.api.schemas.arcs import (
    ArcCreate,
    ArcOut,
    ArcPointCreate,
    ArcPointOut,
    ArcPointUpdate,
    ArcTypeCreate,
    ArcTypeOut,
    ArcTypeUpdate,
    ArcUpdate,
)
from storymaster.model.database.schema import base as schema
from storymaster.sync_server.database import get_db

router = APIRouter(prefix="/api/v1", tags=["arcs"])


# ---------------------------------------------------------------------------
# ArcType (scoped per setting)
# ---------------------------------------------------------------------------


@router.get("/settings/{setting_id}/arc-types", response_model=list[ArcTypeOut])
def list_arc_types(
    setting: schema.Setting = Depends(require_setting),
    db: Session = Depends(get_db),
) -> list[schema.ArcType]:
    stmt = (
        select(schema.ArcType)
        .where(schema.ArcType.setting_id == setting.id)
        .order_by(schema.ArcType.id)
    )
    return list(db.execute(stmt).scalars().all())


@router.post(
    "/settings/{setting_id}/arc-types",
    response_model=ArcTypeOut,
    status_code=status.HTTP_201_CREATED,
)
def create_arc_type(
    payload: ArcTypeCreate,
    setting: schema.Setting = Depends(require_setting),
    db: Session = Depends(get_db),
) -> schema.ArcType:
    arc_type = schema.ArcType(
        name=payload.name, description=payload.description, setting_id=setting.id
    )
    db.add(arc_type)
    db.commit()
    db.refresh(arc_type)
    return arc_type


@router.patch("/arc-types/{arc_type_id}", response_model=ArcTypeOut)
def update_arc_type(
    arc_type_id: int,
    payload: ArcTypeUpdate,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.ArcType:
    arc_type = _require_arc_type(db, user, arc_type_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        if v is None:
            continue
        setattr(arc_type, k, v)
    db.commit()
    db.refresh(arc_type)
    return arc_type


@router.delete("/arc-types/{arc_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_arc_type(
    arc_type_id: int,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    arc_type = _require_arc_type(db, user, arc_type_id)
    db.delete(arc_type)
    db.commit()


# ---------------------------------------------------------------------------
# Arcs (scoped per storyline)
# ---------------------------------------------------------------------------


@router.get("/storylines/{storyline_id}/arcs", response_model=list[ArcOut])
def list_arcs(
    storyline: schema.Storyline = Depends(require_storyline),
    db: Session = Depends(get_db),
) -> list[schema.LitographyArc]:
    stmt = (
        select(schema.LitographyArc)
        .where(schema.LitographyArc.storyline_id == storyline.id)
        .order_by(schema.LitographyArc.id)
    )
    return list(db.execute(stmt).scalars().all())


@router.post(
    "/storylines/{storyline_id}/arcs",
    response_model=ArcOut,
    status_code=status.HTTP_201_CREATED,
)
def create_arc(
    payload: ArcCreate,
    storyline: schema.Storyline = Depends(require_storyline),
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.LitographyArc:
    arc_type = _require_arc_type(db, user, payload.arc_type_id)
    arc = schema.LitographyArc(
        title=payload.title,
        description=payload.description,
        arc_type_id=arc_type.id,
        storyline_id=storyline.id,
    )
    db.add(arc)
    db.flush()
    _replace_actor_links(db, user, arc.id, payload.actor_ids)
    db.commit()
    db.refresh(arc)
    return arc


@router.get("/arcs/{arc_id}", response_model=ArcOut)
def get_arc(arc: schema.LitographyArc = Depends(require_arc)) -> schema.LitographyArc:
    return arc


@router.patch("/arcs/{arc_id}", response_model=ArcOut)
def update_arc(
    payload: ArcUpdate,
    arc: schema.LitographyArc = Depends(require_arc),
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.LitographyArc:
    data = payload.model_dump(exclude_unset=True)
    if "arc_type_id" in data and data["arc_type_id"] is not None:
        _require_arc_type(db, user, data["arc_type_id"])
    actor_ids = data.pop("actor_ids", None)
    for k, v in data.items():
        if v is None:
            continue
        setattr(arc, k, v)
    if actor_ids is not None:
        _replace_actor_links(db, user, arc.id, actor_ids)
    db.commit()
    db.refresh(arc)
    return arc


@router.delete("/arcs/{arc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_arc(
    arc: schema.LitographyArc = Depends(require_arc), db: Session = Depends(get_db)
):
    db.delete(arc)
    db.commit()


# ---------------------------------------------------------------------------
# Arc points
# ---------------------------------------------------------------------------


@router.get("/arcs/{arc_id}/points", response_model=list[ArcPointOut])
def list_arc_points(
    arc: schema.LitographyArc = Depends(require_arc), db: Session = Depends(get_db)
) -> list[schema.ArcPoint]:
    stmt = (
        select(schema.ArcPoint)
        .where(schema.ArcPoint.arc_id == arc.id)
        .order_by(schema.ArcPoint.order_index, schema.ArcPoint.id)
    )
    return list(db.execute(stmt).scalars().all())


@router.post(
    "/arcs/{arc_id}/points",
    response_model=ArcPointOut,
    status_code=status.HTTP_201_CREATED,
)
def create_arc_point(
    payload: ArcPointCreate,
    arc: schema.LitographyArc = Depends(require_arc),
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.ArcPoint:
    if payload.node_id is not None:
        _assert_node_in_storyline(db, user, payload.node_id, arc.storyline_id)
    point = schema.ArcPoint(
        arc_id=arc.id,
        title=payload.title,
        order_index=payload.order_index,
        description=payload.description,
        emotional_state=payload.emotional_state,
        character_relationships=payload.character_relationships,
        goals=payload.goals,
        internal_conflict=payload.internal_conflict,
        node_id=payload.node_id,
    )
    db.add(point)
    db.commit()
    db.refresh(point)
    return point


@router.patch("/arc-points/{arc_point_id}", response_model=ArcPointOut)
def update_arc_point(
    arc_point_id: int,
    payload: ArcPointUpdate,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.ArcPoint:
    point = _require_arc_point(db, user, arc_point_id)
    data = payload.model_dump(exclude_unset=True)
    if "node_id" in data and data["node_id"] is not None:
        arc = db.get(schema.LitographyArc, point.arc_id)
        _assert_node_in_storyline(db, user, data["node_id"], arc.storyline_id)
    for k, v in data.items():
        setattr(point, k, v)
    db.commit()
    db.refresh(point)
    return point


@router.delete("/arc-points/{arc_point_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_arc_point(
    arc_point_id: int,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    point = _require_arc_point(db, user, arc_point_id)
    db.delete(point)
    db.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_arc_type(
    db: Session, user: schema.User, arc_type_id: int
) -> schema.ArcType:
    arc_type = db.get(schema.ArcType, arc_type_id)
    if arc_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arc type not found")
    setting = db.get(schema.Setting, arc_type.setting_id)
    if setting is None or setting.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arc type not found")
    return arc_type


def _require_arc_point(
    db: Session, user: schema.User, arc_point_id: int
) -> schema.ArcPoint:
    point = db.get(schema.ArcPoint, arc_point_id)
    if point is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arc point not found")
    arc = db.get(schema.LitographyArc, point.arc_id)
    if arc is None or arc.storyline is None or arc.storyline.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arc point not found")
    return point


def _replace_actor_links(
    db: Session, user: schema.User, arc_id: int, actor_ids: list[int]
) -> None:
    """Wipe and recreate ArcToActor links. Validates each actor belongs to a
    setting the user owns to avoid cross-tenant linkage."""
    db.execute(
        select(schema.ArcToActor).where(schema.ArcToActor.arc_id == arc_id)
    )  # ensure flush before delete via ORM
    db.query(schema.ArcToActor).filter(schema.ArcToActor.arc_id == arc_id).delete(
        synchronize_session=False
    )
    for actor_id in actor_ids:
        actor = db.get(schema.Actor, actor_id)
        if actor is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Actor {actor_id} not found"
            )
        setting = db.get(schema.Setting, actor.setting_id)
        if setting is None or setting.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Actor {actor_id} not found"
            )
        db.add(schema.ArcToActor(arc_id=arc_id, actor_id=actor_id))


def _assert_node_in_storyline(
    db: Session, user: schema.User, node_id: int, storyline_id: int
) -> None:
    node = db.get(schema.LitographyNode, node_id)
    if (
        node is None
        or node.storyline_id != storyline_id
        or node.storyline is None
        or node.storyline.user_id != user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node {node_id} not in this storyline",
        )

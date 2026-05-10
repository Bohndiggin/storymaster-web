"""Generic Lorekeeper CRUD over world-building entity tables.

The set of "lorekeeper entity" tables is the subset of `BaseModel._table_to_class_map`
that has a `setting_id` column AND represents a user-visible world-building entity
(actors, factions, locations, races, classes, etc.) — junction-only tables and
litography/sync internals are intentionally excluded.

All endpoints scope by `setting_id` in the URL; that path segment is the
authorization gate (via `require_setting`).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import inspect as sa_inspect, select
from sqlalchemy.orm import Session

from storymaster.api.authz import require_setting
from storymaster.api.deps import get_current_user
from storymaster.model.common.common_model import BaseModel
from storymaster.model.database.schema import base as schema
from storymaster.sync_server.database import get_db

router = APIRouter(prefix="/api/v1", tags=["lorekeeper"])


# Allowlisted entity tables. Each must have a `setting_id` column. We exclude
# tables already covered by dedicated routers (storyline, setting, litography_*,
# arc_*) and pure plumbing (sync_*, user_session).
LOREKEEPER_TABLES: frozenset[str] = frozenset(
    {
        "class",
        "background",
        "race",
        "sub_race",
        "alignment",
        "stat",
        "actor",
        "actor_a_on_b_relations",
        "actor_to_race",
        "actor_to_class",
        "actor_to_stat",
        "actor_to_skills",
        "skills",
        "faction",
        "faction_a_on_b_relations",
        "faction_members",
        "location_",
        "location_to_faction",
        "location_dungeon",
        "location_city",
        "location_city_districts",
        "residents",
        "location_flora_fauna",
        "location_a_on_b_relations",
        "location_geographic_relations",
        "location_political_relations",
        "location_economic_relations",
        "location_hierarchy",
        "history",
        "history_actor",
        "history_location",
        "history_faction",
        "history_object",
        "history_world_data",
        "object_",
        "object_to_owner",
        "world_data",
    }
)


# A small list of high-signal entity tables used by the Storyweaver
# autocomplete / auto-tagging flow. The "name" column on each is what gets
# matched against prose. Junction tables are excluded.
STORYWEAVER_ENTITY_TABLES: tuple[str, ...] = (
    "actor",
    "faction",
    "location_",
    "object_",
    "race",
    "sub_race",
    "class",
    "background",
    "skills",
    "history",
    "world_data",
)


def _orm_class(table_name: str):
    cls = BaseModel._table_to_class_map.get(table_name)
    if cls is None or table_name not in LOREKEEPER_TABLES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown lorekeeper table: {table_name!r}",
        )
    return cls


def _to_dict(row: Any) -> dict[str, Any]:
    if hasattr(row, "as_dict"):
        return row.as_dict()
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


# ---------------------------------------------------------------------------
# Schema discovery
# ---------------------------------------------------------------------------


@router.get("/lorekeeper/schema")
def lorekeeper_schema(_: schema.User = Depends(get_current_user)) -> dict[str, Any]:
    """Return per-table column + FK info for the frontend to render forms.

    Cheap to compute; cache on the client by setting/version.
    """
    out: dict[str, dict[str, Any]] = {}
    for table_name in sorted(LOREKEEPER_TABLES):
        cls = BaseModel._table_to_class_map[table_name]
        columns: list[dict[str, Any]] = []
        for col in cls.__table__.columns:
            entry: dict[str, Any] = {
                "name": col.name,
                "type": str(col.type).lower(),
                "nullable": bool(col.nullable),
                "primary_key": bool(col.primary_key),
            }
            if col.foreign_keys:
                fk = next(iter(col.foreign_keys))
                entry["foreign_key"] = {
                    "table": fk.column.table.name,
                    "column": fk.column.name,
                }
            columns.append(entry)
        out[table_name] = {"columns": columns}
    return {"tables": out}


# ---------------------------------------------------------------------------
# Per-table CRUD
# ---------------------------------------------------------------------------


@router.get("/settings/{setting_id}/entities/{table_name}")
def list_entities(
    table_name: str,
    setting: schema.Setting = Depends(require_setting),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    cls = _orm_class(table_name)
    stmt = select(cls).where(cls.setting_id == setting.id).order_by(cls.id)
    return [_to_dict(r) for r in db.execute(stmt).scalars().all()]


@router.post(
    "/settings/{setting_id}/entities/{table_name}",
    status_code=status.HTTP_201_CREATED,
)
def create_entity(
    table_name: str,
    payload: dict[str, Any],
    setting: schema.Setting = Depends(require_setting),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    cls = _orm_class(table_name)
    # Strip server-managed fields the client shouldn't be setting.
    safe = {k: v for k, v in payload.items() if k not in {"id", "setting_id", "created_at",
                                                          "updated_at", "deleted_at",
                                                          "version", "sync_uuid"}}
    safe["setting_id"] = setting.id
    try:
        row = cls(**safe)
    except TypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_dict(row)


@router.get("/settings/{setting_id}/entities/{table_name}/{row_id}")
def get_entity(
    table_name: str,
    row_id: int,
    setting: schema.Setting = Depends(require_setting),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = _require_entity_row(db, _orm_class(table_name), setting.id, row_id)
    return _to_dict(row)


@router.patch("/settings/{setting_id}/entities/{table_name}/{row_id}")
def update_entity(
    table_name: str,
    row_id: int,
    payload: dict[str, Any],
    setting: schema.Setting = Depends(require_setting),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    cls = _orm_class(table_name)
    row = _require_entity_row(db, cls, setting.id, row_id)
    columns = cls.__table__.columns
    for k, v in payload.items():
        if k in {"id", "setting_id", "created_at", "updated_at", "deleted_at",
                 "version", "sync_uuid"}:
            continue
        if k not in columns:
            continue
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return _to_dict(row)


@router.delete(
    "/settings/{setting_id}/entities/{table_name}/{row_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_entity(
    table_name: str,
    row_id: int,
    setting: schema.Setting = Depends(require_setting),
    db: Session = Depends(get_db),
):
    cls = _orm_class(table_name)
    row = _require_entity_row(db, cls, setting.id, row_id)
    db.delete(row)
    db.commit()


# ---------------------------------------------------------------------------
# Combined entity index for Storyweaver autocomplete / auto-tagging
# ---------------------------------------------------------------------------


@router.get("/settings/{setting_id}/entities")
def list_all_entities(
    setting: schema.Setting = Depends(require_setting),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Combined list of named world entities for the editor's autocomplete.

    Each entry has `entity_type`, `id`, and `name` — the only fields the editor
    actually needs to compile its match patterns. Detail fetches go to the
    per-table endpoints.
    """
    out: list[dict[str, Any]] = []
    for table_name in STORYWEAVER_ENTITY_TABLES:
        cls = BaseModel._table_to_class_map.get(table_name)
        if cls is None or not _has_name_column(cls):
            continue
        name_col = _resolve_name_expression(cls)
        stmt = (
            select(cls.id, name_col)
            .where(cls.setting_id == setting.id)
            .order_by(name_col)
        )
        for row in db.execute(stmt).all():
            row_id, name = row
            if name is None:
                continue
            out.append({"entity_type": table_name, "id": row_id, "name": name})
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_entity_row(db: Session, cls, setting_id: int, row_id: int):
    row = db.get(cls, row_id)
    if row is None or getattr(row, "setting_id", None) != setting_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{cls.__tablename__} not found"
        )
    return row


def _has_name_column(cls) -> bool:
    cols = {c.name for c in cls.__table__.columns}
    return "name" in cols or "first_name" in cols or "title" in cols


def _resolve_name_expression(cls):
    """Pick the column to use as the display "name" for autocomplete.

    `first_name` ranks above `title` because actors have both — and `title` on
    Actor is the formal title (Lord, Captain), not the display name.
    """
    cols = {c.name for c in cls.__table__.columns}
    if "name" in cols:
        return cls.__table__.c.name
    if "first_name" in cols:
        return cls.__table__.c.first_name
    return cls.__table__.c.title

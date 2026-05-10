"""LitographyNotes — the per-node pinboard. Distinct from Storyweaver
documents (those land in Phase 6 with their own table and router).

Also exposes note↔entity associations under
`/api/v1/notes/{note_id}/associations`. Authorization for those rides on the
parent note's storyline — same as the note's own endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel as _PydanticBase
from sqlalchemy import select
from sqlalchemy.orm import Session

from storymaster.api.authz import get_storyline_owned_node, require_note, require_storyline
from storymaster.api.deps import get_current_user
from storymaster.api.schemas.notes import NoteCreate, NoteOut, NoteUpdate
from storymaster.model.common.common_model import BaseModel as _BaseModel
from storymaster.model.database.schema import base as schema
from storymaster.sync_server.database import get_db

router = APIRouter(prefix="/api/v1", tags=["notes"])


# Reuse BaseModel's dispatcher table so the wire format and the local model
# stay locked together — adding a new entity type only touches that map.
_ASSOC_MAP: dict[str, tuple[type, str]] = _BaseModel._NOTE_ASSOCIATION_MAP

# Plural keys the existing controller / desktop reads.
_PLURALS: dict[str, str] = {
    "actor": "actors",
    "background": "backgrounds",
    "class": "classes",
    "faction": "factions",
    "history": "histories",
    "location": "locations",
    "object": "objects",
    "race": "races",
    "skill": "skills",
    "sub_race": "sub_races",
    "world_data": "world_data",
}


class AssociationCreate(_PydanticBase):
    entity_type: str
    entity_id: int


def _coerce_note_type(value: str) -> schema.NoteType:
    try:
        return schema.NoteType(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid note_type: {value!r}",
        ) from exc


@router.get("/storylines/{storyline_id}/notes", response_model=list[NoteOut])
def list_notes(
    storyline: schema.Storyline = Depends(require_storyline),
    db: Session = Depends(get_db),
) -> list[schema.LitographyNotes]:
    stmt = (
        select(schema.LitographyNotes)
        .where(schema.LitographyNotes.storyline_id == storyline.id)
        .order_by(schema.LitographyNotes.id)
    )
    return list(db.execute(stmt).scalars().all())


@router.post(
    "/storylines/{storyline_id}/notes",
    response_model=NoteOut,
    status_code=status.HTTP_201_CREATED,
)
def create_note(
    payload: NoteCreate,
    storyline: schema.Storyline = Depends(require_storyline),
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.LitographyNotes:
    node = get_storyline_owned_node(db, user, payload.linked_node_id)
    if node.storyline_id != storyline.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="linked_node_id is not in this storyline",
        )
    note = schema.LitographyNotes(
        title=payload.title,
        description=payload.description,
        note_type=_coerce_note_type(payload.note_type),
        linked_node_id=node.id,
        storyline_id=storyline.id,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.get("/notes/{note_id}", response_model=NoteOut)
def get_note(note: schema.LitographyNotes = Depends(require_note)) -> schema.LitographyNotes:
    return note


@router.patch("/notes/{note_id}", response_model=NoteOut)
def update_note(
    payload: NoteUpdate,
    note: schema.LitographyNotes = Depends(require_note),
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.LitographyNotes:
    data = payload.model_dump(exclude_unset=True)
    if "note_type" in data and data["note_type"] is not None:
        data["note_type"] = _coerce_note_type(data["note_type"])
    if "linked_node_id" in data and data["linked_node_id"] is not None:
        node = get_storyline_owned_node(db, user, data["linked_node_id"])
        if node.storyline_id != note.storyline_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Node is not in this storyline",
            )
    for k, v in data.items():
        if v is None:
            continue
        setattr(note, k, v)
    db.commit()
    db.refresh(note)
    return note


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note: schema.LitographyNotes = Depends(require_note),
    db: Session = Depends(get_db),
):
    db.delete(note)
    db.commit()


# ---------------------------------------------------------------------------
# Note ↔ entity associations
# ---------------------------------------------------------------------------


@router.get("/notes/{note_id}/associations")
def list_note_associations(
    note: schema.LitographyNotes = Depends(require_note),
    db: Session = Depends(get_db),
) -> dict[str, list[dict[str, Any]]]:
    """Every entity-association row for a note, grouped by plural entity-type
    key. The dict shape mirrors `BaseModel.get_note_associations` so the
    desktop's existing usage doesn't need to branch on backend."""
    out: dict[str, list[dict[str, Any]]] = {plural: [] for plural in _PLURALS.values()}
    for entity_type, (cls, _) in _ASSOC_MAP.items():
        rows = db.execute(select(cls).where(cls.note_id == note.id)).scalars().all()
        out[_PLURALS[entity_type]] = [_dump_assoc(r) for r in rows]
    return out


@router.post(
    "/notes/{note_id}/associations",
    status_code=status.HTTP_201_CREATED,
)
def create_note_association(
    payload: AssociationCreate,
    note: schema.LitographyNotes = Depends(require_note),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    mapping = _ASSOC_MAP.get(payload.entity_type)
    if mapping is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown entity type: {payload.entity_type!r}",
        )
    cls, fk_col = mapping
    row = cls(**{"note_id": note.id, fk_col: payload.entity_id})
    db.add(row)
    db.commit()
    db.refresh(row)
    return _dump_assoc(row)


@router.delete(
    "/notes/{note_id}/associations/{entity_type}/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_note_association(
    entity_type: str,
    entity_id: int,
    note: schema.LitographyNotes = Depends(require_note),
    db: Session = Depends(get_db),
):
    mapping = _ASSOC_MAP.get(entity_type)
    if mapping is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown entity type")
    cls, fk_col = mapping
    row = (
        db.execute(
            select(cls).where(
                cls.note_id == note.id, getattr(cls, fk_col) == entity_id
            )
        )
        .scalar_one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Association not found")
    db.delete(row)
    db.commit()


def _dump_assoc(row: Any) -> dict[str, Any]:
    """Return the row's columns as a JSON-friendly dict (lean — no relationships)."""
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}

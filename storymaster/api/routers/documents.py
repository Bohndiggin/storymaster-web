"""Storyweaver document CRUD.

Documents are user-owned (each Document has a user_id). Optional storyline_id
and setting_id let the client filter the inbox per-storyline / per-setting.
The HTML body and entity_map blob are dumb columns; the editor handles the
content shape.

Markdown round-tripping with the desktop's `.storyweaver` ZIP format is
deferred — see PHASE6_TODO.md.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from storymaster.api.authz import require_setting, require_storyline
from storymaster.api.deps import get_current_user
from storymaster.api.schemas.documents import (
    DocumentCreate,
    DocumentOut,
    DocumentSummary,
    DocumentUpdate,
)
from storymaster.model.database.schema import base as schema
from storymaster.sync_server.database import get_db

router = APIRouter(prefix="/api/v1", tags=["documents"])


def _require_document(
    db: Session, user: schema.User, document_id: int
) -> schema.Document:
    doc = db.get(schema.Document, document_id)
    if doc is None or doc.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


def _validate_scope(
    db: Session,
    user: schema.User,
    storyline_id: int | None,
    setting_id: int | None,
) -> None:
    """Ensure any storyline_id / setting_id the client passed is theirs.

    A user shouldn't be able to drop a doc into another tenant's storyline
    even by guessing ids."""
    if storyline_id is not None:
        storyline = db.get(schema.Storyline, storyline_id)
        if storyline is None or storyline.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Storyline not found"
            )
    if setting_id is not None:
        setting = db.get(schema.Setting, setting_id)
        if setting is None or setting.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found"
            )


@router.get("/documents", response_model=list[DocumentSummary])
def list_documents(
    storyline_id: int | None = Query(default=None),
    setting_id: int | None = Query(default=None),
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[schema.Document]:
    """Inbox for the current user. Filters apply additively when set."""
    stmt = select(schema.Document).where(schema.Document.user_id == user.id)
    if storyline_id is not None:
        stmt = stmt.where(schema.Document.storyline_id == storyline_id)
    if setting_id is not None:
        stmt = stmt.where(schema.Document.setting_id == setting_id)
    stmt = stmt.order_by(schema.Document.updated_at.desc())
    return list(db.execute(stmt).scalars().all())


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: DocumentCreate,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.Document:
    _validate_scope(db, user, payload.storyline_id, payload.setting_id)
    doc = schema.Document(
        user_id=user.id,
        title=payload.title,
        content_html=payload.content_html,
        entity_map_json=payload.entity_map_json,
        storyline_id=payload.storyline_id,
        setting_id=payload.setting_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: int,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.Document:
    return _require_document(db, user, document_id)


@router.patch("/documents/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: int,
    payload: DocumentUpdate,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.Document:
    doc = _require_document(db, user, document_id)
    data = payload.model_dump(exclude_unset=True)
    if "storyline_id" in data or "setting_id" in data:
        _validate_scope(
            db,
            user,
            data.get("storyline_id", doc.storyline_id),
            data.get("setting_id", doc.setting_id),
        )
    for k, v in data.items():
        setattr(doc, k, v)
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = _require_document(db, user, document_id)
    db.delete(doc)
    db.commit()

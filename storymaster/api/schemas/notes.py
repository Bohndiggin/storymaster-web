"""LitographyNotes DTOs (the per-node pinboard, not Storyweaver documents)."""

from __future__ import annotations

from pydantic import BaseModel

from storymaster.api.schemas.common import TimestampedDTO


class NoteCreate(BaseModel):
    title: str
    description: str | None = None
    note_type: str  # NoteType: what/why/how/when/where/other
    linked_node_id: int


class NoteUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    note_type: str | None = None
    linked_node_id: int | None = None


class NoteOut(TimestampedDTO):
    id: int
    title: str
    description: str | None
    note_type: str
    linked_node_id: int
    storyline_id: int

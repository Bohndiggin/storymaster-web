"""Storyweaver Document DTOs."""

from __future__ import annotations

from pydantic import BaseModel

from storymaster.api.schemas.common import TimestampedDTO


class DocumentCreate(BaseModel):
    title: str = "Untitled"
    content_html: str = ""
    entity_map_json: str = "{}"
    storyline_id: int | None = None
    setting_id: int | None = None


class DocumentUpdate(BaseModel):
    title: str | None = None
    content_html: str | None = None
    entity_map_json: str | None = None
    storyline_id: int | None = None
    setting_id: int | None = None


class DocumentOut(TimestampedDTO):
    id: int
    user_id: int
    storyline_id: int | None
    setting_id: int | None
    title: str
    content_html: str
    entity_map_json: str


class DocumentSummary(TimestampedDTO):
    """Lightweight payload for the document-list sidebar — no body."""

    id: int
    user_id: int
    storyline_id: int | None
    setting_id: int | None
    title: str

"""Arcs DTOs: ArcType, LitographyArc, ArcPoint, ArcToActor, ArcToNode."""

from __future__ import annotations

from pydantic import BaseModel, Field

from storymaster.api.schemas.common import TimestampedDTO


class ArcTypeCreate(BaseModel):
    name: str
    description: str | None = None


class ArcTypeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ArcTypeOut(TimestampedDTO):
    id: int
    name: str
    description: str | None
    setting_id: int


class ArcCreate(BaseModel):
    title: str
    description: str | None = None
    arc_type_id: int
    actor_ids: list[int] = Field(default_factory=list)


class ArcUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    arc_type_id: int | None = None
    actor_ids: list[int] | None = None


class ArcOut(TimestampedDTO):
    id: int
    title: str
    description: str | None
    arc_type_id: int
    storyline_id: int


class ArcPointCreate(BaseModel):
    title: str
    order_index: int = 0
    description: str | None = None
    emotional_state: str | None = None
    character_relationships: str | None = None
    goals: str | None = None
    internal_conflict: str | None = None
    node_id: int | None = None


class ArcPointUpdate(BaseModel):
    title: str | None = None
    order_index: int | None = None
    description: str | None = None
    emotional_state: str | None = None
    character_relationships: str | None = None
    goals: str | None = None
    internal_conflict: str | None = None
    node_id: int | None = None


class ArcPointOut(TimestampedDTO):
    id: int
    arc_id: int
    title: str
    order_index: int
    description: str | None
    emotional_state: str | None
    character_relationships: str | None
    goals: str | None
    internal_conflict: str | None
    node_id: int | None

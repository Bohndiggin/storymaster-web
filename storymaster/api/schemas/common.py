"""Shared DTO mixins."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base for response DTOs that read attributes from SQLAlchemy ORM objects."""

    model_config = ConfigDict(from_attributes=True)


class TimestampedDTO(ORMModel):
    sync_uuid: str
    created_at: datetime
    updated_at: datetime
    version: int

"""Storyline + Setting + StorylineToSetting DTOs."""

from __future__ import annotations

from pydantic import BaseModel

from storymaster.api.schemas.common import TimestampedDTO


class StorylineCreate(BaseModel):
    name: str | None = None
    description: str | None = None


class StorylineUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class StorylineOut(TimestampedDTO):
    id: int
    name: str | None
    description: str | None
    user_id: int


class SettingCreate(BaseModel):
    name: str | None = None
    description: str | None = None


class SettingUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class SettingOut(TimestampedDTO):
    id: int
    name: str | None
    description: str | None
    user_id: int


class StorylineSettingLink(BaseModel):
    setting_id: int

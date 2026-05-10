"""Storylines, Settings, and the link table between them.

Each storyline and setting belongs to exactly one user. List endpoints scope
automatically; detail/update/delete go through `require_storyline` /
`require_setting`, which 404 (not 403) on unowned IDs so callers cannot probe
for other users' data.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from storymaster.api.authz import require_setting, require_storyline
from storymaster.api.deps import get_current_user
from storymaster.api.schemas.storylines import (
    SettingCreate,
    SettingOut,
    SettingUpdate,
    StorylineCreate,
    StorylineOut,
    StorylineSettingLink,
    StorylineUpdate,
)
from storymaster.model.database.schema import base as schema
from storymaster.sync_server.database import get_db

router = APIRouter(prefix="/api/v1", tags=["storylines"])


# ---------------------------------------------------------------------------
# Storylines
# ---------------------------------------------------------------------------


@router.get("/storylines", response_model=list[StorylineOut])
def list_storylines(
    user: schema.User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[schema.Storyline]:
    stmt = (
        select(schema.Storyline)
        .where(schema.Storyline.user_id == user.id)
        .order_by(schema.Storyline.id)
    )
    return list(db.execute(stmt).scalars().all())


@router.post("/storylines", response_model=StorylineOut, status_code=status.HTTP_201_CREATED)
def create_storyline(
    payload: StorylineCreate,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.Storyline:
    storyline = schema.Storyline(
        name=payload.name, description=payload.description, user_id=user.id
    )
    db.add(storyline)
    db.commit()
    db.refresh(storyline)
    return storyline


@router.get("/storylines/{storyline_id}", response_model=StorylineOut)
def get_storyline(
    storyline: schema.Storyline = Depends(require_storyline),
) -> schema.Storyline:
    return storyline


@router.patch("/storylines/{storyline_id}", response_model=StorylineOut)
def update_storyline(
    payload: StorylineUpdate,
    storyline: schema.Storyline = Depends(require_storyline),
    db: Session = Depends(get_db),
) -> schema.Storyline:
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(storyline, k, v)
    db.commit()
    db.refresh(storyline)
    return storyline


@router.delete("/storylines/{storyline_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_storyline(
    storyline: schema.Storyline = Depends(require_storyline),
    db: Session = Depends(get_db),
):
    db.delete(storyline)
    db.commit()


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@router.get("/settings", response_model=list[SettingOut])
def list_settings(
    user: schema.User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[schema.Setting]:
    stmt = (
        select(schema.Setting)
        .where(schema.Setting.user_id == user.id)
        .order_by(schema.Setting.id)
    )
    return list(db.execute(stmt).scalars().all())


@router.post("/settings", response_model=SettingOut, status_code=status.HTTP_201_CREATED)
def create_setting(
    payload: SettingCreate,
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schema.Setting:
    setting = schema.Setting(
        name=payload.name, description=payload.description, user_id=user.id
    )
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


@router.get("/settings/{setting_id}", response_model=SettingOut)
def get_setting(setting: schema.Setting = Depends(require_setting)) -> schema.Setting:
    return setting


@router.patch("/settings/{setting_id}", response_model=SettingOut)
def update_setting(
    payload: SettingUpdate,
    setting: schema.Setting = Depends(require_setting),
    db: Session = Depends(get_db),
) -> schema.Setting:
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(setting, k, v)
    db.commit()
    db.refresh(setting)
    return setting


@router.delete("/settings/{setting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_setting(
    setting: schema.Setting = Depends(require_setting),
    db: Session = Depends(get_db),
):
    db.delete(setting)
    db.commit()


# ---------------------------------------------------------------------------
# Storyline ↔ Setting linkage
# ---------------------------------------------------------------------------


@router.get("/storylines/{storyline_id}/settings", response_model=list[SettingOut])
def list_settings_for_storyline(
    storyline: schema.Storyline = Depends(require_storyline),
    db: Session = Depends(get_db),
) -> list[schema.Setting]:
    stmt = (
        select(schema.Setting)
        .join(
            schema.StorylineToSetting,
            schema.StorylineToSetting.setting_id == schema.Setting.id,
        )
        .where(schema.StorylineToSetting.storyline_id == storyline.id)
        .order_by(schema.Setting.id)
    )
    return list(db.execute(stmt).scalars().all())


@router.post(
    "/storylines/{storyline_id}/settings",
    status_code=status.HTTP_204_NO_CONTENT,
)
def link_storyline_to_setting(
    payload: StorylineSettingLink,
    storyline: schema.Storyline = Depends(require_storyline),
    user: schema.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    setting = db.get(schema.Setting, payload.setting_id)
    if setting is None or setting.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")

    existing = db.execute(
        select(schema.StorylineToSetting).where(
            schema.StorylineToSetting.storyline_id == storyline.id,
            schema.StorylineToSetting.setting_id == setting.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None

    db.add(schema.StorylineToSetting(storyline_id=storyline.id, setting_id=setting.id))
    db.commit()


@router.delete(
    "/storylines/{storyline_id}/settings/{setting_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unlink_storyline_from_setting(
    storyline: schema.Storyline = Depends(require_storyline),
    setting: schema.Setting = Depends(require_setting),
    db: Session = Depends(get_db),
):
    link = db.execute(
        select(schema.StorylineToSetting).where(
            schema.StorylineToSetting.storyline_id == storyline.id,
            schema.StorylineToSetting.setting_id == setting.id,
        )
    ).scalar_one_or_none()
    if link is None:
        return None
    db.delete(link)
    db.commit()

"""Lore-package discovery + import endpoints.

The actual import logic lives in `storymaster.api.lore_packages`. The router
is thin — it owns auth, transaction boundary, and DTO shape.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Reject pathologically large uploads outright — a normal pack is under a few
# hundred KB; 5 MB is generous and protects the server from OOM on hostile
# uploads.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

from storymaster.api import lore_packages
from storymaster.api.authz import require_setting
from storymaster.api.deps import get_current_user
from storymaster.model.database.schema import base as schema
from storymaster.sync_server.database import get_db

router = APIRouter(prefix="/api/v1", tags=["lore-packages"])


class LorePackageOut(BaseModel):
    slug: str
    display_name: str
    description: str
    category: str
    version: str


class LorePackageImportPayload(BaseModel):
    package: str  # slug, e.g. "fantasy_races"


class LorePackageImportResult(BaseModel):
    package: str
    imported: int
    skipped_duplicates: int
    imported_by_table: dict[str, int]


@router.get("/lore-packages", response_model=list[LorePackageOut])
def list_lore_packages(
    _: schema.User = Depends(get_current_user),
) -> list[LorePackageOut]:
    return [
        LorePackageOut(
            slug=p.slug,
            display_name=p.display_name,
            description=p.description,
            category=p.category,
            version=p.version,
        )
        for p in lore_packages.list_packages()
    ]


@router.post(
    "/settings/{setting_id}/lore-packages/import",
    response_model=LorePackageImportResult,
)
def import_lore_package(
    payload: LorePackageImportPayload,
    setting: schema.Setting = Depends(require_setting),
    db: Session = Depends(get_db),
) -> LorePackageImportResult:
    try:
        result = lore_packages.import_package(db, payload.package, setting.id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {exc}",
        ) from exc
    db.commit()
    return LorePackageImportResult(
        package=result.package_slug,
        imported=result.imported,
        skipped_duplicates=result.skipped_duplicates,
        imported_by_table=result.imported_by_table,
    )


@router.post(
    "/settings/{setting_id}/lore-packages/upload",
    response_model=LorePackageImportResult,
)
async def upload_lore_package(
    file: UploadFile,
    setting: schema.Setting = Depends(require_setting),
    db: Session = Depends(get_db),
) -> LorePackageImportResult:
    """Import a user-uploaded JSON pack into the active setting.

    The file is never persisted to disk — we parse, import inside the request
    transaction, and discard. That keeps uploads cheap and avoids leaving
    half-validated packs in the bundled packages directory.
    """
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Upload exceeds {MAX_UPLOAD_BYTES} bytes",
        )
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Empty upload",
        )

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File is not valid UTF-8",
        ) from exc

    try:
        package_data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid JSON: {exc.msg} (line {exc.lineno})",
        ) from exc

    # Slug for the response — uses the uploaded filename, sanitized down to a
    # display label. Falls back to "uploaded" when there's no useful name.
    raw_name = (file.filename or "uploaded").rsplit("/", 1)[-1]
    slug = raw_name.removesuffix(".json") or "uploaded"

    try:
        result = lore_packages.import_package_data(
            db, package_data, setting.id, slug=slug
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {exc}",
        ) from exc
    db.commit()
    return LorePackageImportResult(
        package=result.package_slug,
        imported=result.imported,
        skipped_duplicates=result.skipped_duplicates,
        imported_by_table=result.imported_by_table,
    )

"""Shared FastAPI dependencies: current-user resolution that accepts either a
session cookie (web) or a Bearer device token (mobile sync clients)."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from storymaster.api.sessions import SESSION_COOKIE_NAME, get_user_for_session
from storymaster.model.database.schema.base import SyncDevice, User
from storymaster.sync_server.database import get_db


def _user_from_bearer(db: Session, token: str) -> User | None:
    """Resolve a device token to its owning user.

    Devices created before per-user ownership existed have user_id=NULL — those
    must be re-paired (or backfilled) after the migration. We deliberately fail
    here rather than silently granting access.
    """
    if not token:
        return None
    stmt = select(SyncDevice).where(
        SyncDevice.auth_token == token, SyncDevice.is_active.is_(True)
    )
    device = db.execute(stmt).scalar_one_or_none()
    if device is None or device.user_id is None:
        return None
    user = db.get(User, device.user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie_token:
        user = get_user_for_session(db, cookie_token)
        if user is not None:
            return user

    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        user = _user_from_bearer(db, token)
        if user is not None:
            return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None

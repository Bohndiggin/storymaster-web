"""Auth endpoints: login, logout, current user, change password.

Sessions live server-side keyed by an opaque token in an HTTP-only cookie. No
public registration — admins create accounts via `scripts/create_admin.py`.
"""

import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from storymaster.api.deps import get_current_user
from storymaster.api.security import hash_password, needs_rehash, verify_password
from storymaster.api.sessions import (
    SESSION_COOKIE_NAME,
    SESSION_LIFETIME,
    create_session,
    revoke_session,
)
from storymaster.model.database.schema.base import User, UserSession
from storymaster.sync_server.database import get_db

MIN_PASSWORD_LENGTH = 8

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    is_active: bool


class LoginResponse(BaseModel):
    user: UserOut


def _secure_cookies() -> bool:
    """Whether to mark the session cookie `Secure` (HTTPS-only).

    Defaults to True so a misconfigured deploy fails closed. The dev
    workflow runs over plaintext http://127.0.0.1, so opt-out via
    STORYMASTER_SECURE_COOKIES=false. Anything reachable from the
    public internet should keep the default."""
    raw = os.getenv("STORYMASTER_SECURE_COOKIES", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=_secure_cookies(),
        path="/",
    )


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest, response: Response, db: Session = Depends(get_db)
) -> LoginResponse:
    stmt = select(User).where(User.username == payload.username)
    user = db.execute(stmt).scalar_one_or_none()
    if user is None or not user.is_active or user.password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not verify_password(user.password_hash, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
        db.commit()

    session = create_session(db, user)
    _set_session_cookie(response, session.session_id)
    return LoginResponse(
        user=UserOut(id=user.id, username=user.username, is_active=user.is_active)
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> Response:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        revoke_session(db, token)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(id=user.id, username=user.username, is_active=user.is_active)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if len(payload.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"New password must be at least {MIN_PASSWORD_LENGTH} characters",
        )
    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    user.password_hash = hash_password(payload.new_password)

    # Revoke every session except the caller's so other browsers/devices have
    # to re-authenticate with the new password.
    current_token = request.cookies.get(SESSION_COOKIE_NAME)
    sessions = db.execute(
        select(UserSession).where(UserSession.user_id == user.id)
    ).scalars().all()
    for session in sessions:
        if session.session_id != current_token:
            db.delete(session)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)

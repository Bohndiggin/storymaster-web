"""Auth endpoints: login, logout, current user.

Sessions live server-side keyed by an opaque token in an HTTP-only cookie. No
public registration — admins create accounts via `scripts/create_admin.py`.
"""

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
from storymaster.model.database.schema.base import User
from storymaster.sync_server.database import get_db

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


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        samesite="lax",
        # `secure` flag is enabled in production via reverse proxy / env-driven config.
        secure=False,
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

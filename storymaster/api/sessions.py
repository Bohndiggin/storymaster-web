"""Server-side session store backed by the `user_session` table.

Sessions are opaque random tokens stored in an HTTP-only cookie. Server-side
state lets us revoke immediately on logout and keeps cookies short. A sliding
expiry refreshes `expires_at` each time we observe a request, so an active user
stays logged in indefinitely while idle ones drop out.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from storymaster.model.database.schema.base import User, UserSession

SESSION_COOKIE_NAME = "storymaster_session"
SESSION_LIFETIME = timedelta(days=14)
SESSION_TOKEN_BYTES = 32


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def create_session(db: Session, user: User) -> UserSession:
    session = UserSession(
        session_id=_generate_token(),
        user_id=user.id,
        expires_at=_now() + SESSION_LIFETIME,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_user_for_session(db: Session, session_id: str) -> User | None:
    """Look up a session by its cookie token, returning the active user.

    Returns None if the session is missing, expired, or its user is inactive.
    Touches `last_seen_at` and slides `expires_at` forward on a hit.
    """
    if not session_id:
        return None
    stmt = (
        select(UserSession)
        .where(UserSession.session_id == session_id)
        .where(UserSession.deleted_at.is_(None))
    )
    session = db.execute(stmt).scalar_one_or_none()
    if session is None:
        return None
    now = _now()
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        db.delete(session)
        db.commit()
        return None
    if session.user is None or not session.user.is_active:
        return None
    session.last_seen_at = now
    session.expires_at = now + SESSION_LIFETIME
    db.commit()
    return session.user


def revoke_session(db: Session, session_id: str) -> None:
    if not session_id:
        return
    stmt = select(UserSession).where(UserSession.session_id == session_id)
    session = db.execute(stmt).scalar_one_or_none()
    if session is not None:
        db.delete(session)
        db.commit()


def purge_expired(db: Session) -> int:
    """Delete sessions whose `expires_at` has passed. Safe to call periodically."""
    now = _now()
    stmt = select(UserSession).where(UserSession.expires_at <= now)
    expired = db.execute(stmt).scalars().all()
    for session in expired:
        db.delete(session)
    if expired:
        db.commit()
    return len(expired)

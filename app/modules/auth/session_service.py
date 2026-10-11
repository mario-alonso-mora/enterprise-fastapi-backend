"""Transactional authentication sessions and refresh-token rotation."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import AuthSession, RefreshToken
from app.modules.users.models import User

SESSION_LIFETIME = timedelta(days=14)


class InvalidRefreshToken(Exception):
    """Invalid, expired or revoked refresh token."""


class RefreshTokenReused(InvalidRefreshToken):
    """A previously consumed refresh token was presented again."""


@dataclass(frozen=True)
class SessionCredentials:
    session_id: uuid.UUID
    user_id: uuid.UUID
    refresh_token: str
    expires_at: datetime


def _hash_token(token: str) -> str:
    if not isinstance(token, str) or not 32 <= len(token) <= 256:
        raise InvalidRefreshToken

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, _hash_token(raw)


def _as_utc(value: datetime) -> datetime:
    """Normalize database timestamps to timezone-aware UTC."""
    # SQLite drops timezone information; our timestamps are stored as UTC.
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def _is_expired(value: datetime, now: datetime) -> bool:
    return _as_utc(value) <= now


def create_session(user: User, db: Session) -> SessionCredentials:
    """Create a persistent session after successful authentication.

    Owns the transaction: commits on success, rolls back on failure.
    """
    if not user.is_active:
        raise InvalidRefreshToken

    now = datetime.now(UTC)
    expires_at = now + SESSION_LIFETIME
    raw, digest = _new_token()

    try:
        session = AuthSession(
            user_id=user.id,
            expires_at=expires_at,
        )
        db.add(session)
        db.flush()

        db.add(
            RefreshToken(
                session_id=session.id,
                token_hash=digest,
                expires_at=expires_at,
            )
        )

        db.commit()

        return SessionCredentials(
            session_id=session.id,
            user_id=user.id,
            refresh_token=raw,
            expires_at=expires_at,
        )
    except Exception:
        db.rollback()
        raise


def rotate_refresh_token(
    raw_token: str,
    db: Session,
) -> SessionCredentials:
    """Consume a refresh token and issue a replacement atomically.

    PostgreSQL serializes rotations of the same session using
    SELECT FOR UPDATE on auth_sessions.

    Reuse of a consumed token revokes its entire session.
    """
    try:
        digest = _hash_token(raw_token)

        # Fetch only the session ID before taking the lock.
        # Do not load a RefreshToken ORM object yet.
        session_id = db.scalar(
            select(RefreshToken.session_id).where(RefreshToken.token_hash == digest)
        )

        if session_id is None:
            raise InvalidRefreshToken

        # All token rotations belonging to the same session
        # must acquire this lock before checking consumption.
        session = db.scalar(
            select(AuthSession).where(AuthSession.id == session_id).with_for_update()
        )

        if session is None:
            raise InvalidRefreshToken

        # Read token state AFTER acquiring the session lock.
        token = db.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == digest,
                RefreshToken.session_id == session.id,
            )
        )

        if token is None:
            raise InvalidRefreshToken

        now = datetime.now(UTC)

        if token.consumed_at is not None:
            # Commit revocation BEFORE raising the exception.
            # Otherwise an HTTP handler rollback would undo it.
            if session.revoked_at is None:
                session.revoked_at = now
                db.commit()

            raise RefreshTokenReused

        if session.revoked_at is not None:
            raise InvalidRefreshToken

        if _is_expired(session.expires_at, now):
            raise InvalidRefreshToken

        if _is_expired(token.expires_at, now):
            raise InvalidRefreshToken

        user = db.get(User, session.user_id)

        if user is None or not user.is_active:
            raise InvalidRefreshToken

        replacement_raw, replacement_hash = _new_token()

        token.consumed_at = now

        db.add(
            RefreshToken(
                session_id=session.id,
                token_hash=replacement_hash,
                expires_at=session.expires_at,
            )
        )

        db.commit()

        return SessionCredentials(
            session_id=session.id,
            user_id=user.id,
            refresh_token=replacement_raw,
            expires_at=_as_utc(session.expires_at),
        )

    except Exception:
        db.rollback()
        raise


def revoke_session(
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session,
) -> bool:
    """Revoke a session belonging to the specified user.

    Returns True when revoked and False when absent or
    already revoked. Owns the database transaction.
    """
    try:
        session = db.scalar(
            select(AuthSession)
            .where(
                AuthSession.id == session_id,
                AuthSession.user_id == user_id,
            )
            .with_for_update()
        )

        if session is None or session.revoked_at is not None:
            db.rollback()
            return False

        session.revoked_at = datetime.now(UTC)
        db.commit()
        return True

    except Exception:
        db.rollback()
        raise

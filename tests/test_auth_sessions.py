"""Functional tests for persistent authentication sessions."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401
from app.db.base import Base
from app.modules.auth.models import AuthSession, RefreshToken
from app.modules.auth.session_service import (
    InvalidRefreshToken,
    RefreshTokenReused,
    create_session,
    revoke_session,
    rotate_refresh_token,
)
from app.modules.organizations.models import Organization
from app.modules.users.models import User


@pytest.fixture
def db_user():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    try:
        with Session(engine, expire_on_commit=False) as db:
            organization = Organization(
                name="Authentication Tests",
                slug="auth-tests",
            )
            db.add(organization)
            db.flush()

            user = User(
                organization_id=organization.id,
                email="auth-tests@example.com",
                password_hash="test-only",
                role="admin",
            )
            db.add(user)
            db.commit()

            yield db, user
    finally:
        engine.dispose()


def test_create_session_stores_only_token_hash(db_user):
    db, user = db_user
    issued = create_session(user, db)

    session = db.get(AuthSession, issued.session_id)
    token = db.scalar(select(RefreshToken).where(RefreshToken.session_id == issued.session_id))

    assert session is not None
    assert token is not None
    assert session.user_id == user.id
    assert issued.user_id == user.id
    assert token.token_hash == hashlib.sha256(issued.refresh_token.encode()).hexdigest()
    assert issued.refresh_token != token.token_hash
    assert session.revoked_at is None


def test_rotation_consumes_previous_token(db_user):
    db, user = db_user
    first = create_session(user, db)
    second = rotate_refresh_token(first.refresh_token, db)

    assert second.session_id == first.session_id
    assert second.refresh_token != first.refresh_token
    assert second.expires_at == first.expires_at

    old_hash = hashlib.sha256(first.refresh_token.encode()).hexdigest()

    previous = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == old_hash))

    assert previous is not None
    assert previous.consumed_at is not None


def test_reused_token_revokes_entire_session(db_user):
    db, user = db_user
    first = create_session(user, db)
    second = rotate_refresh_token(first.refresh_token, db)

    with pytest.raises(RefreshTokenReused):
        rotate_refresh_token(first.refresh_token, db)

    session = db.get(AuthSession, first.session_id)
    assert session.revoked_at is not None

    with pytest.raises(InvalidRefreshToken):
        rotate_refresh_token(second.refresh_token, db)


def test_expired_session_cannot_rotate(db_user):
    db, user = db_user
    issued = create_session(user, db)

    session = db.get(AuthSession, issued.session_id)
    session.expires_at = datetime.now(UTC) - timedelta(seconds=5)
    db.commit()

    with pytest.raises(InvalidRefreshToken):
        rotate_refresh_token(issued.refresh_token, db)


def test_inactive_user_cannot_rotate(db_user):
    db, user = db_user
    issued = create_session(user, db)

    user.is_active = False
    db.commit()

    with pytest.raises(InvalidRefreshToken):
        rotate_refresh_token(issued.refresh_token, db)


def test_unknown_and_malformed_tokens_are_rejected(db_user):
    db, _ = db_user

    for token in ("invalid", secrets.token_urlsafe(32)):
        with pytest.raises(InvalidRefreshToken):
            rotate_refresh_token(token, db)


def test_replay_does_not_revoke_other_sessions(db_user):
    db, user = db_user
    first = create_session(user, db)
    independent = create_session(user, db)

    rotate_refresh_token(first.refresh_token, db)

    with pytest.raises(RefreshTokenReused):
        rotate_refresh_token(first.refresh_token, db)

    renewed = rotate_refresh_token(independent.refresh_token, db)

    assert renewed.session_id == independent.session_id


def test_revoke_session_invalidates_refresh(db_user):
    db, user = db_user
    target = create_session(user, db)
    independent = create_session(user, db)

    assert revoke_session(target.session_id, user.id, db)

    with pytest.raises(InvalidRefreshToken):
        rotate_refresh_token(target.refresh_token, db)

    renewed = rotate_refresh_token(independent.refresh_token, db)
    assert renewed.session_id == independent.session_id


def test_revoke_session_checks_ownership(db_user):
    db, user = db_user
    issued = create_session(user, db)

    assert (
        revoke_session(
            issued.session_id,
            uuid.uuid4(),
            db,
        )
        is False
    )

    renewed = rotate_refresh_token(issued.refresh_token, db)
    assert renewed.session_id == issued.session_id


def test_revoke_session_is_idempotent(db_user):
    db, user = db_user
    issued = create_session(user, db)

    assert revoke_session(issued.session_id, user.id, db)
    assert not revoke_session(issued.session_id, user.id, db)
    assert not revoke_session(uuid.uuid4(), user.id, db)

    session = db.get(AuthSession, issued.session_id)
    assert session.revoked_at is not None

"""Real PostgreSQL locking and refresh-token concurrency tests."""

import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

import app.db.models  # noqa: F401
from app.db.base import Base
from app.modules.auth.models import AuthSession, RefreshToken
from app.modules.auth.session_service import (
    InvalidRefreshToken,
    RefreshTokenReused,
    create_session,
    rotate_refresh_token,
)
from app.modules.organizations.models import Organization
from app.modules.users.models import User


@pytest.fixture(scope="module")
def pg_factory():
    source = os.getenv("AUTH_TEST_ADMIN_DATABASE_URL")
    if not source:
        pytest.skip("PostgreSQL integration URL not configured")

    url = make_url(source)

    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"db", "localhost", "127.0.0.1"}
        or url.database not in {"enterprise", "enterprise_test"}
    ):
        pytest.fail("Unexpected PostgreSQL configuration")

    name = "enterprise_auth_ci_" + uuid.uuid4().hex[:12]

    admin = create_engine(
        url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
    )
    engine = None
    created = False

    try:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
            created = True

        engine = create_engine(
            url.set(database=name),
            pool_size=5,
            max_overflow=5,
            isolation_level="READ COMMITTED",
        )

        Base.metadata.create_all(engine)

        factory = sessionmaker(
            bind=engine,
            expire_on_commit=False,
        )

        yield engine, factory

    finally:
        if engine is not None:
            engine.dispose()

        if created:
            with admin.connect() as connection:
                connection.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')

        admin.dispose()


def make_user(factory):
    unique = uuid.uuid4().hex

    with factory() as db:
        organization = Organization(
            name="Auth Integration Tests",
            slug=unique,
        )
        db.add(organization)
        db.flush()

        user = User(
            organization_id=organization.id,
            email=f"{unique}@example.test",
            password_hash="test-only",
            role="admin",
        )
        db.add(user)
        db.commit()

        return user.id


def test_concurrent_rotation_and_replay_revocation(pg_factory):
    _, factory = pg_factory
    user_id = make_user(factory)

    def rotate(raw, barrier):
        with factory() as db:
            barrier.wait(timeout=15)

            try:
                result = rotate_refresh_token(raw, db)
                return "success", result.refresh_token
            except RefreshTokenReused:
                return "reused", None

    for _ in range(10):
        with factory() as db:
            user = db.get(User, user_id)
            issued = create_session(user, db)

        barrier = threading.Barrier(2)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(rotate, issued.refresh_token, barrier) for _ in range(2)]
            results = [future.result(timeout=30) for future in futures]

        assert sorted(result[0] for result in results) == [
            "reused",
            "success",
        ]

        replacement = next(token for status, token in results if status == "success")

        with factory() as db:
            session = db.get(AuthSession, issued.session_id)

            assert session.revoked_at is not None

            count = db.scalar(
                select(func.count())
                .select_from(RefreshToken)
                .where(RefreshToken.session_id == issued.session_id)
            )

            assert count == 2

            with pytest.raises(InvalidRefreshToken):
                rotate_refresh_token(replacement, db)

    # Replaying one session must not revoke other sessions.
    with factory() as db:
        user = db.get(User, user_id)
        independent = create_session(user, db)

    with factory() as db:
        renewed = rotate_refresh_token(independent.refresh_token, db)
        assert renewed.session_id == independent.session_id


def test_for_update_blocks_competing_rotation(pg_factory):
    engine, factory = pg_factory
    user_id = make_user(factory)

    with factory() as db:
        issued = create_session(db.get(User, user_id), db)

    reached_lock = threading.Event()

    @event.listens_for(engine, "before_cursor_execute")
    def observe_lock(conn, cursor, statement, parameters, context, many):
        sql = statement.upper()
        if (
            threading.current_thread().name.startswith("auth-lock-worker")
            and "FOR UPDATE" in sql
            and "AUTH_SESSIONS" in sql
        ):
            reached_lock.set()

    def worker():
        with factory() as db:
            return rotate_refresh_token(issued.refresh_token, db)

    try:
        with factory() as locker:
            locker.execute(
                select(AuthSession.id).where(AuthSession.id == issued.session_id).with_for_update()
            ).scalar_one()

            with ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="auth-lock-worker",
            ) as pool:
                future = pool.submit(worker)

                try:
                    assert reached_lock.wait(timeout=10), "Worker never reached SELECT FOR UPDATE"

                    time.sleep(0.2)

                    assert not future.done(), "Rotation finished while session was locked"
                finally:
                    # Always release the lock before waiting on worker.
                    locker.commit()

                renewed = future.result(timeout=20)

                assert renewed.session_id == issued.session_id

    finally:
        event.remove(engine, "before_cursor_execute", observe_lock)

    with factory() as db:
        tokens = db.scalars(
            select(RefreshToken).where(RefreshToken.session_id == issued.session_id)
        ).all()

        assert len(tokens) == 2
        assert sum(t.consumed_at is not None for t in tokens) == 1

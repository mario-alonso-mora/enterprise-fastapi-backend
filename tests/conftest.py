import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-only-jwt-secret-with-at-least-32-characters-12345"
os.environ["BOOTSTRAP_KEY"] = "test-only-bootstrap-key-with-at-least-32-characters-12345"

import pytest  # noqa: E402
from fakeredis import FakeRedis  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.db.models  # noqa: E402,F401
from app.core.config import get_settings  # noqa: E402
from app.core.rate_limit import get_redis  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def client():
    database_url = os.getenv("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    if database_url.startswith("sqlite"):
        engine = create_engine(
            database_url, connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    else:
        engine = create_engine(database_url, pool_pre_ping=True)

    # CI also applies Alembic first to verify migration correctness against PostgreSQL.
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    app = create_app()

    def override_get_db():
        with Session(engine) as session:
            yield session

    fake_redis = FakeRedis(decode_responses=True)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: fake_redis
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        fake_redis.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def register(client):
    def _register(slug, email, password="StrongPassword-12345"):
        payload = {
            "organization_name": f"{slug.title()} Inc",
            "organization_slug": slug,
            "admin_email": email,
            "admin_password": password,
        }
        return client.post(
            "/api/v1/auth/register",
            json=payload,
            headers={"X-Bootstrap-Key": get_settings().bootstrap_key.get_secret_value()},
        )

    return _register


@pytest.fixture
def login(client):
    def _login(email, password="StrongPassword-12345"):
        response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _login

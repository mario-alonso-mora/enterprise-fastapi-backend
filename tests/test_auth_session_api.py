"""HTTP tests for session-based authentication."""

from datetime import datetime
from uuid import UUID

import jwt

from app.core.config import get_settings
from app.core.security import create_access_token


def authenticate(client, register):
    response = register(
        "sessions-api",
        "sessions-api@example.com",
    )
    assert response.status_code == 201, response.text

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "sessions-api@example.com",
            "password": "StrongPassword-12345",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_login_creates_refresh_token_and_jwt_session(client, register):
    tokens = authenticate(client, register)

    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] > 0
    assert len(tokens["refresh_token"]) >= 32

    expires_at = datetime.fromisoformat(tokens["session_expires_at"].replace("Z", "+00:00"))
    assert expires_at.tzinfo is not None

    settings = get_settings()
    claims = jwt.decode(
        tokens["access_token"],
        settings.jwt_secret_key.get_secret_value(),
        algorithms=["HS256"],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        leeway=5,
    )

    assert claims["typ"] == "access"
    assert UUID(claims["sid"])


def test_refresh_rotates_credentials(client, register):
    first = authenticate(client, register)

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert response.status_code == 200, response.text

    second = response.json()

    assert second["refresh_token"] != first["refresh_token"]
    assert second["session_expires_at"] == first["session_expires_at"]

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": second["refresh_token"]},
    )
    assert response.status_code == 200, response.text


def test_refresh_replay_revokes_session(client, register):
    first = authenticate(client, register)

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert response.status_code == 200

    second = response.json()

    replay = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert replay.status_code == 401

    blocked = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": second["refresh_token"]},
    )
    assert blocked.status_code == 401


def test_unknown_refresh_is_rejected(client):
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid"},
    )
    assert response.status_code == 401


def test_logout_revokes_only_its_session(client, register):
    first = authenticate(client, register)

    second_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "sessions-api@example.com",
            "password": "StrongPassword-12345",
        },
    )
    assert second_login.status_code == 200
    independent = second_login.json()

    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {first['access_token']}"},
    )
    assert response.status_code == 204
    assert response.content == b""

    blocked = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert blocked.status_code == 401

    surviving = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": independent["refresh_token"]},
    )
    assert surviving.status_code == 200


def test_logout_is_idempotent(client, register):
    tokens = authenticate(client, register)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    for _ in range(2):
        response = client.post(
            "/api/v1/auth/logout",
            headers=headers,
        )
        assert response.status_code == 204
        assert response.content == b""


def test_logout_requires_authenticated_session(client, register):
    missing = client.post("/api/v1/auth/logout")
    assert missing.status_code == 401

    registration = register(
        "legacy-logout",
        "legacy-logout@example.com",
    )
    assert registration.status_code == 201

    user_id = UUID(registration.json()["user_id"])
    legacy_token = create_access_token(user_id, get_settings())

    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {legacy_token}"},
    )
    assert response.status_code == 401


def test_token_responses_are_not_cacheable(client, register):
    registration = register(
        "cache-headers",
        "cache-headers@example.com",
    )
    assert registration.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "cache-headers@example.com",
            "password": "StrongPassword-12345",
        },
    )
    assert login_response.status_code == 200

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": login_response.json()["refresh_token"],
        },
    )
    assert refresh_response.status_code == 200

    for result in (login_response, refresh_response):
        assert result.headers["Cache-Control"] == "no-store"
        assert result.headers["Pragma"] == "no-cache"

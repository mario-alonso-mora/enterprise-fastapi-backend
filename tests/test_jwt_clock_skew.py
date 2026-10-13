"""Regression tests for JWT clock skew and security boundaries."""

from datetime import UTC, datetime

import jwt
import pytest

from app.core.config import get_settings


def make_claims(user_id, issued_offset, expiry_offset):
    settings = get_settings()
    now = int(datetime.now(UTC).timestamp())

    return {
        "sub": str(user_id),
        "iat": now + issued_offset,
        "exp": now + expiry_offset,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "typ": "access",
    }


def active_session_id(client, email):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword-12345"},
    )
    assert response.status_code == 200

    settings = get_settings()
    claims = jwt.decode(
        response.json()["access_token"],
        settings.jwt_secret_key.get_secret_value(),
        algorithms=["HS256"],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )
    return claims["sid"]


@pytest.mark.parametrize(
    ("issued_offset", "expiry_offset", "expected"),
    [
        (3, 180, 200),
        (40, 180, 401),
        (-120, -60, 401),
    ],
    ids=[
        "small-clock-skew-accepted",
        "large-future-iat-rejected",
        "expired-token-rejected",
    ],
)
def test_jwt_clock_skew_and_expiry(
    client,
    register,
    issued_offset,
    expiry_offset,
    expected,
):
    registration = register("acme", "owner@acme.example.com")
    assert registration.status_code == 201

    settings = get_settings()
    claims = make_claims(
        registration.json()["user_id"],
        issued_offset,
        expiry_offset,
    )

    claims["sid"] = active_session_id(client, "owner@acme.example.com")

    token = jwt.encode(
        claims,
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )

    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == expected, response.text


def test_jwt_invalid_signature_still_rejected(client, register):
    registration = register("acme", "owner@acme.example.com")
    assert registration.status_code == 201

    claims = make_claims(
        registration.json()["user_id"],
        0,
        180,
    )

    claims["sid"] = active_session_id(client, "owner@acme.example.com")

    token = jwt.encode(
        claims,
        "different-test-only-signing-secret",
        algorithm="HS256",
    )

    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401

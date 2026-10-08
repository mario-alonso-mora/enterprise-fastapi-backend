"""HTTP integration tests for authentication rate limiting."""

from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.rate_limit import get_redis


def test_login_rate_limit_returns_429(client):
    payload = {
        "email": "unknown@example.com",
        "password": "WrongPassword-12345",
    }

    for _ in range(5):
        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 401, response.text

    blocked = client.post("/api/v1/auth/login", json=payload)

    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Too many requests"
    assert 1 <= int(blocked.headers["Retry-After"]) <= 60


def test_registration_rate_limit_returns_429(client):
    payload = {
        "organization_name": "Acme Ltd",
        "organization_slug": "acme",
        "admin_email": "owner@acme.example.com",
        "admin_password": "StrongPassword-12345",
    }

    # No bootstrap key: requests are rejected but still counted.
    for _ in range(3):
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 401

    blocked = client.post("/api/v1/auth/register", json=payload)

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1


def test_client_cannot_bypass_limit_with_forwarded_headers(client):
    payload = {
        "email": "unknown@example.com",
        "password": "WrongPassword-12345",
    }

    for number in range(5):
        response = client.post(
            "/api/v1/auth/login",
            json=payload,
            headers={"X-Forwarded-For": f"192.0.2.{number + 1}"},
        )
        assert response.status_code == 401

    response = client.post(
        "/api/v1/auth/login",
        json=payload,
        headers={"X-Forwarded-For": "198.51.100.99"},
    )

    assert response.status_code == 429


def test_login_and_registration_have_independent_limits(client):
    login_payload = {
        "email": "unknown@example.com",
        "password": "WrongPassword-12345",
    }

    for _ in range(5):
        assert (
            client.post(
                "/api/v1/auth/login",
                json=login_payload,
            ).status_code
            == 401
        )

    assert (
        client.post(
            "/api/v1/auth/login",
            json=login_payload,
        ).status_code
        == 429
    )

    registration = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Acme Ltd",
            "organization_slug": "acme",
            "admin_email": "owner@acme.example.com",
            "admin_password": "StrongPassword-12345",
        },
    )

    # The independent registration counter is not exhausted.
    assert registration.status_code == 401


def test_redis_failure_is_fail_closed(client):
    class UnavailableRedis:
        def eval(self, *args, **kwargs):
            raise RedisConnectionError("Simulated Redis outage")

    client.app.dependency_overrides[get_redis] = lambda: UnavailableRedis()

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "unknown@example.com",
            "password": "WrongPassword-12345",
        },
    )

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "1"
    assert "Simulated Redis outage" not in response.text

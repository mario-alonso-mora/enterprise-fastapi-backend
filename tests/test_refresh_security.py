"""HTTP security tests for the refresh endpoint."""

from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.config import get_settings
from app.core.rate_limit import get_redis


def test_refresh_rate_limit_returns_429(client):
    limit = get_settings().rate_limit_refresh_per_minute
    endpoint = "/api/v1/auth/refresh"
    payload = {"refresh_token": "invalid"}

    for _ in range(limit):
        response = client.post(endpoint, json=payload)
        assert response.status_code == 401

    blocked = client.post(endpoint, json=payload)

    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Too many requests"
    assert 1 <= int(blocked.headers["Retry-After"]) <= 60

    # Refresh and login must have independent counters.
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "unknown@example.com",
            "password": "WrongPassword-12345",
        },
    )
    assert login.status_code == 401


def test_refresh_cannot_bypass_limit_with_forwarded_headers(client):
    limit = get_settings().rate_limit_refresh_per_minute
    endpoint = "/api/v1/auth/refresh"
    payload = {"refresh_token": "invalid"}

    for number in range(limit):
        response = client.post(
            endpoint,
            json=payload,
            headers={"X-Forwarded-For": f"192.0.2.{number + 1}"},
        )
        assert response.status_code == 401

    blocked = client.post(
        endpoint,
        json=payload,
        headers={"X-Forwarded-For": "198.51.100.99"},
    )

    assert blocked.status_code == 429


def test_refresh_redis_failure_is_fail_closed(client):
    class UnavailableRedis:
        def eval(self, *args, **kwargs):
            raise RedisConnectionError("Simulated Redis outage")

    client.app.dependency_overrides[get_redis] = lambda: UnavailableRedis()

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid"},
    )

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "1"
    assert "Simulated Redis outage" not in response.text


def test_refresh_rejects_oversized_token(client):
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "x" * 257},
    )

    assert response.status_code == 422

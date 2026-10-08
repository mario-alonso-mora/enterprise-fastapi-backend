"""Shared Redis counter test, enabled when TEST_REDIS_URL is configured."""

import os
from uuid import uuid4

import pytest
from redis import Redis

from app.core.rate_limit import check_limit


@pytest.mark.skipif(
    not os.getenv("TEST_REDIS_URL"),
    reason="Real Redis integration requires TEST_REDIS_URL",
)
def test_atomic_limit_is_shared_between_redis_connections():
    url = os.environ["TEST_REDIS_URL"]

    first = Redis.from_url(url, socket_timeout=2)
    second = Redis.from_url(url, socket_timeout=2)

    key = f"enterprise:test-rate-limit:{uuid4()}"

    try:
        assert check_limit(first, key, 2)[0] is True
        assert check_limit(second, key, 2)[0] is True

        allowed, remaining_ms = check_limit(first, key, 2)

        assert allowed is False
        assert 0 < remaining_ms <= 60_000
    finally:
        first.delete(key)
        first.close()
        second.close()

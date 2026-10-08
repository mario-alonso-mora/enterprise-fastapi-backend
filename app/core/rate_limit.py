"""Shared, atomic Redis rate limiting for authentication endpoints."""

import hashlib
import logging
from functools import lru_cache

from fastapi import Depends, HTTPException, Request
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import Settings, get_settings

logger = logging.getLogger("enterprise.rate_limit")

# INCR, expiration and result are evaluated atomically by Redis.
LIMIT_SCRIPT = """
local count = redis.call("INCR", KEYS[1])
local window_ms = tonumber(ARGV[2])

if count == 1 then
    redis.call("PEXPIRE", KEYS[1], window_ms)
end

local remaining_ms = redis.call("PTTL", KEYS[1])

if remaining_ms < 0 then
    redis.call("PEXPIRE", KEYS[1], window_ms)
    remaining_ms = window_ms
end

if count > tonumber(ARGV[1]) then
    return {0, remaining_ms}
end

return {1, remaining_ms}
"""


@lru_cache
def get_redis() -> Redis:
    settings = get_settings()
    return Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=1,
        socket_timeout=1,
        decode_responses=True,
    )


def check_limit(
    store: Redis,
    key: str,
    limit: int,
    window_seconds: int = 60,
) -> tuple[bool, int]:
    result = store.eval(
        LIMIT_SCRIPT,
        1,
        key,
        limit,
        window_seconds * 1000,
    )
    return bool(int(result[0])), int(result[1])


def enforce_limit(
    request: Request,
    store: Redis,
    scope: str,
    limit: int,
) -> None:
    # Never trust client-supplied X-Forwarded-For directly.
    client_ip = request.client.host if request.client else "unknown"
    identifier = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()

    key = f"enterprise:rate-limit:v1:{scope}:{identifier}"

    try:
        allowed, remaining_ms = check_limit(store, key, limit)
    except (RedisError, OSError, ValueError, TypeError, IndexError) as exc:
        logger.error("rate_limit_store_unavailable")
        raise HTTPException(
            status_code=503,
            detail="Authentication temporarily unavailable",
            headers={"Retry-After": "1"},
        ) from exc

    if not allowed:
        retry_after = max(1, (remaining_ms + 999) // 1000)

        raise HTTPException(
            status_code=429,
            detail="Too many requests",
            headers={"Retry-After": str(retry_after)},
        )


def limit_login(
    request: Request,
    store: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> None:
    enforce_limit(
        request,
        store,
        "login",
        settings.rate_limit_login_per_minute,
    )


def limit_register(
    request: Request,
    store: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> None:
    enforce_limit(
        request,
        store,
        "register",
        settings.rate_limit_register_per_minute,
    )

# Authentication Rate Limiting

## Purpose

Protect authentication endpoints against excessive requests using
a shared Redis-backed fixed-window rate limiter.

## Protected endpoints

- POST /api/v1/auth/login
  - Default: 5 requests per 60 seconds per client IP.

- POST /api/v1/auth/register
  - Default: 3 requests per 60 seconds per client IP.

Both limits are configurable using environment variables.

## Implementation

- Redis stores counters with a 60-second expiration.
- Redis Lua scripting makes increments and expiration atomic.
- All API instances sharing Redis observe the same counters.
- Login and registration use independent counters.
- Each counter begins its window with the first request.
- Request limits apply to successful and unsuccessful attempts.

## HTTP responses

- Within limit: original endpoint response.
- Limit exceeded: HTTP 429 with Retry-After.
- Redis unavailable: HTTP 503, fail closed.

Errors do not expose Redis connection details.

## Client identification

The limiter uses the ASGI request client address.

Untrusted X-Forwarded-For values are not read by the limiter.

For deployment behind a reverse proxy, configure trusted proxy
addresses explicitly at the ASGI server or infrastructure layer.

Shared NAT addresses may cause multiple legitimate users to
share a limit.

This IP-based rate limiter does not provide account-based
lockout or complete protection against distributed attacks.

## Operational considerations

The local Redis service is internal to Docker Compose and is
not published to the host.

Local Redis persistence is disabled, so counters are reset
when Redis restarts.

For production deployments, provide a monitored shared Redis
service, appropriate access controls, and an eviction policy
that does not unexpectedly remove active rate-limit keys.

## Testing

- FakeRedis isolates rate limits between HTTP test cases.
- Tests cover HTTP 429 and Retry-After.
- Tests verify X-Forwarded-For does not bypass limits.
- Tests verify independent login and registration counters.
- Tests verify HTTP 503 when Redis is unavailable.
- A separate test checks counter sharing against real Redis.

## Future work

- Optional per-account throttling.
- Trusted reverse-proxy deployment configuration.
- Metrics and alerting for rejected requests.
- Load and concurrent-request testing.

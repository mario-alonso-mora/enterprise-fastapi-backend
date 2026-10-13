# v0.6.0 — Observability and Operational Security

## Overview

Version 0.6.0 introduces structured HTTP logging, request
correlation, safe unexpected-error responses and Prometheus
HTTP metrics.

The implementation builds on the existing authentication,
RBAC, session management and multi-tenant architecture.

## 1. Structured HTTP logging

HTTP requests generate JSON log events containing:

- UTC timestamp
- Log level
- Event type
- Request ID (UUID)
- HTTP method
- Normalized route
- HTTP status code
- Request duration in milliseconds

Request logs use INFO, WARNING or ERROR according to
their status code.

Query-string values are excluded from the structured
HTTP request events.

Logging remains partially structured: logs produced by
other libraries are not automatically converted to JSON.

## 2. Request correlation

Each request receives a generated UUID and exposes it
through the X-Request-ID response header.

Customer audit events reuse the request identifier.

This permits correlation between responses, application
logs and existing audit records.

## 3. Unexpected errors

Unhandled application exceptions produce an HTTP 500
response containing:

- detail: Internal server error
- request_id: UUID identifying the failed request

The corresponding structured error event contains
the exception class name, not the exception message.

HTTP responses do not expose application stack traces
through this handler.

This does not guarantee coverage of failures occurring
outside the middleware or after a response has started
streaming.

## 4. Prometheus metrics

The application provides:

- enterprise_http_requests_total
- enterprise_http_request_duration_seconds

The request counter is labeled by method, route and status
code. The duration histogram is labeled by method and route.

The histogram supports latency distributions, request
counts and duration aggregations.

Metric labels use route patterns rather than raw URLs.

Unknown HTTP methods are grouped under OTHER.
Unmatched paths use the /unmatched label.

Tenant identifiers, user emails, access tokens and query
parameters must not be included as metric labels.

## 5. Monitoring authentication

Endpoint:

GET /internal/metrics

The endpoint does not accept organization administrators'
JWTs as monitoring authorization.

Instead, it uses the dedicated environment variable:

METRICS_SCRAPE_TOKEN

Behavior:

- Unset: HTTP 404, endpoint disabled.
- Missing or invalid Bearer token: HTTP 401 when enabled.
- Correct monitoring Bearer token: HTTP 200.
- Configured token must contain at least 32 characters.

The secret must never be committed to Git or included in
application logs, documentation examples or screenshots.

Monitoring uses:

Authorization: Bearer <monitoring-secret>

Generate credentials using a cryptographically secure
random generator and distribute them through a secrets
manager or another secure deployment mechanism.

## 6. Production access restrictions

The monitoring credential is not a substitute for network
security.

Restrict /internal/metrics to trusted monitoring
infrastructure and use TLS for transmission.

Do not expose this endpoint to the public internet.

Apply credential rotation and access controls as part
of the deployment procedure.

## 7. Deployment limitations

The current metrics registry is held in process memory.

Consequences:

- Metrics reset on application restart.
- Multiple application processes have separate registries.
- Aggregate multi-worker metrics are not implemented.
- Historical monitoring requires an external collector.
- Prometheus/Grafana deployment is outside this release.

Production deployments with multiple workers need an
explicit aggregation strategy before treating these
metrics as a complete service-wide view.

## 8. Local verification

Validation performed on 2026-10-13:

- Full automated suite: 61 passed.
- Ruff lint: passed.
- Ruff format: passed.
- PostgreSQL integration: passed using temporary databases.
- Redis integration: passed using test DB 15.
- Transaction rollback tests: passed.
- Alembic upgrade head: passed.
- Alembic check: no upgrade operations detected.
- Alembic current: 0003 (head).
- Alembic temporary database: removed after validation.

One non-blocking Starlette/httpx deprecation warning remains.

Final verification after the package version bump to 0.6.0:

- Installed package version confirmed: 0.6.0.
- Two consecutive complete test runs: 61 passed each.
- Total across both runs: 122 passed, zero failures.
- Six wall-clock versus monotonic-clock offset jumps
  were detected during the two executions.
- Observed jumps were approximately +11.9 and -12.3
  seconds.
- An earlier intermittent HTTP 401 may be related to
  these clock changes; the precise cause remains
  unconfirmed.

Local WSL/Docker clock stability requires investigation.
Do not weaken JWT validation to mask the environmental
timing anomaly.

Independent GitHub Actions validation remains a
release requirement.

## 9. Release status

This document describes the feature-branch implementation
and local verification.

GitHub pull-request checks, release tagging and the
v0.6.0 deployment are separate release gates and must
be verified before declaring the release complete.

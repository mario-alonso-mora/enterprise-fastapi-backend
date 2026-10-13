# Security model

**Scope:** v0.5.0 development branch, locally tested. This document is not a
security certification or production deployment approval.

## Implemented controls

- Organization registration requires a valid `X-Bootstrap-Key`.
- Passwords are stored using Argon2id.
- Access JWTs are signed using HS256 and validate issuer, audience,
  token type and expiration.
- RBAC distinguishes organization `admin` and `member` permissions.
- Tenant-owned resources are filtered using the authenticated user's
  organization, not a client-supplied tenant identifier.
- Cross-tenant customer reads return HTTP 404.
- PostgreSQL constraints protect relational integrity.
- Authentication sessions persist in PostgreSQL.
- Refresh tokens are random and stored only as SHA-256 hashes.
- Sessions have a fixed maximum lifetime of 14 days.
- Every refresh rotates the token. Reuse of a consumed token
  revokes its session.
- PostgreSQL row locks serialize refresh-token rotations.
- Every protected request validates its JWT against the persistent
  session in PostgreSQL, including user ownership, expiration and revocation.
- Logout immediately invalidates subsequent authenticated requests
  using that session, without affecting independent sessions.
- Redis enforces independent per-IP limits: login 5/minute,
  registration 3/minute and refresh 10/minute by default.
- Protected rate-limited authentication endpoints fail closed
  with HTTP 503 when Redis is unavailable.
- Login and refresh responses include `Cache-Control: no-store`
  and `Pragma: no-cache`.
- Local Docker Compose documentation restricts API exposure
  to the loopback interface.

## Session lifecycle and limitations

All protected endpoints require a valid access JWT containing a `sid`
claim identifying an active persistent authentication session.

The session must exist, belong to the JWT subject, not be revoked and
not have expired. The user must also exist and remain active.

Logout revokes the current session. Both refresh tokens and access JWTs
associated with that session are rejected on subsequent authenticated
requests. Requests already in progress are not forcibly cancelled.

A repeated logout using the same revoked access JWT returns HTTP 401.

Legacy access JWTs without `sid` are rejected on all protected routes.
Clients using these tokens must authenticate again after upgrading
to v0.5.0. This is an intentional breaking authentication change.

Each authenticated request requires a session lookup in PostgreSQL.
Database availability and query performance therefore directly affect
authenticated request processing.

Clients must serialize refresh requests for each session.
Concurrent use of the same refresh token can trigger reuse
detection and revoke that session.

Expired session and refresh-token record cleanup still requires
an operational retention policy and maintenance procedure.

## Known risks and production requirements

- Tenant separation is application-level; PostgreSQL Row-Level
  Security is not enabled.
- Rate-limit identity uses the apparent client IP. Trusted-proxy
  and network configuration must be reviewed before public exposure.
  Client-supplied forwarding headers must not be trusted blindly.
- Rate limits do not replace account-level abuse detection.
- Readiness endpoints must be restricted at the network boundary.
- Production TLS, secrets management, monitoring, backups,
  incident response and deployment rollback remain outstanding.
- Authentication correctness tests are not a substitute for an
  independent security review.

## Handling secrets and test data

Never commit `.env`, passwords, private keys, access tokens,
refresh tokens or real customer information.

Use separate securely generated secrets for `JWT_SECRET_KEY`
and `BOOTSTRAP_KEY`, and rotate any exposed credentials.

The standard pytest client fixture drops and recreates tables
when `TEST_DATABASE_URL` is provided. Never point it at a
development or production database containing valuable data.

Dedicated PostgreSQL concurrency tests create and delete their
own temporary databases.

Before deploying publicly, complete threat modelling, configure
trusted network boundaries, validate backups and recovery, and
establish a tested release and rollback procedure.

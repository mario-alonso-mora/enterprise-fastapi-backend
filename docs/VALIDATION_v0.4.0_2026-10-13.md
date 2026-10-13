# v0.4.0 - Local Acceptance Validation

**Date:** 2026-10-13
**Result:** PASS
**Reference commit:** f6d8970
**Release tag:** v0.4.0

## Environment

- Python 3.12 / FastAPI
- PostgreSQL 17
- Redis 7
- Docker Compose
- Alembic migrations
- Local WSL2 environment

## 1. Database backup and recovery

Before upgrading, a PostgreSQL custom-format backup was created.

Validation completed:

- `pg_restore --list` succeeded.
- Backup restored successfully into an isolated temporary database.
- Restored Alembic revision: `0002`.
- Original and restored databases: 5 tables each.
- Original and restored databases: 4 users each.
- Temporary restore database removed after verification.

The backup is stored outside the Git repository.

## 2. Database migration

Migration `0003_auth_sessions` was applied successfully.

Verified results:

- Alembic revision: `0003 (head)`.
- Database tables: 7.
- Existing users preserved: 4.
- New session and refresh-token tables available.

## 3. Docker and API health

The API image was rebuilt and the API container recreated.

Verified:

- PostgreSQL healthy.
- Redis healthy.
- API container running.
- `GET /health/live`: HTTP 200.
- `GET /health/ready`: HTTP 200.
- API Alembic revision: `0003 (head)`.

## 4. Authentication HTTP smoke tests

OpenAPI exposes:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`

Negative security checks:

- Invalid refresh token rejected: HTTP 401.
- Unauthenticated logout rejected: HTTP 401.

## 5. End-to-end authentication validation

A temporary organization and user were created through the running API.

All checks passed:

1. Organization registration: HTTP 201.
2. Login and token issuance: HTTP 200.
3. Refresh-token rotation: HTTP 200.
4. Previous and replacement refresh tokens differed.
5. Logout: HTTP 204.
6. Refresh after logout rejected: HTTP 401.
7. Temporary organization and related records deleted.
8. Original user count preserved: 4.

No access tokens, refresh tokens, passwords or production
credentials are included in this report.

## 6. Continuous integration

GitHub Actions is configured to run on pushes and pull requests.

The CI workflow uses Python 3.12, PostgreSQL 17 and Redis 7
and executes:

- `ruff check .`
- `ruff format --check .`
- `alembic upgrade head`
- `alembic check`
- `pytest -q`

The CI result must be confirmed separately for the new
documentation commit.

## Scope and limitations

This report records successful manual validation in the local
Docker environment. It does not constitute a production
deployment, penetration test or complete security audit.

The PostgreSQL recovery exercise and live HTTP acceptance
tests are manual checks, not automatic CI checks.

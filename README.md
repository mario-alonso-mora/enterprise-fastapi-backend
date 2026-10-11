# Enterprise FastAPI Backend

**Modular multi-tenant REST API built with FastAPI, PostgreSQL and SQLAlchemy 2.**

Enterprise FastAPI Backend implements the foundations of a B2B platform: organization onboarding, authentication, role-based access control (RBAC), tenant-scoped customer operations, schema migrations and automated tests.

The design prioritizes clear authorization boundaries, data integrity and reproducible development workflows.

> **Status: v0.4.0.** Locally validated implementation; **not production-hardened**. Review [Security](docs/SECURITY.md) before exposing the API to the internet.

## Engineering highlights

- **Tenant isolation:** customer queries use the organization resolved from the authenticated user, not a client-provided organization ID.
- **Authentication:** Argon2id, JWT access tokens, persistent sessions, hashed rotating refresh tokens, replay detection and logout.
- **Authorization:** `admin` and `member` roles. Members can read customers; only admins can modify them.
- **Persistence:** PostgreSQL 17, SQLAlchemy 2 and Alembic migrations; database constraints protect integrity.
- **API design:** Pydantic schemas, versioned routes, pagination and OpenAPI/Swagger UI.
- **Operations:** Docker Compose, liveness/readiness endpoints, request IDs and structured HTTP logging.
- **Quality:** Ruff, pytest, SQLite and PostgreSQL integration checks, and GitHub Actions.

## Technology stack

| Area | Technology |
| --- | --- |
| Runtime | Python 3.12, FastAPI, Uvicorn |
| Data | PostgreSQL 17, SQLAlchemy 2, psycopg 3, Alembic |
| Security | PyJWT (HS256), Argon2id, RBAC |
| Validation | Pydantic, pydantic-settings |
| Tooling | Docker Compose, pytest, HTTPX, Ruff, GitHub Actions |

## Architecture

The project follows a **modular monolith** approach. SQLAlchemy sessions are synchronous by design for the current workload; async processing is not introduced without a measured need.

```text
HTTP -> FastAPI routers / Pydantic schemas
                |
        Authentication / RBAC
                |
        Feature modules (auth, users, customers)
                |
        Application services / tenant-scoped repository
                |
        SQLAlchemy models + sessions
                |
             PostgreSQL
```

The code is organized under `app/api`, `app/core`, `app/db` and `app/modules`. Migrations live in `alembic/`, tests in `tests/`, and architecture/security documentation in `docs/`.

See [ADR 0001](docs/adr/0001-modular-monolith.md).

## Quick start

Requirements: Docker Engine and Docker Compose. The local API listens on `127.0.0.1:8000`.

```bash
cp .env.example .env
# Edit .env: change the database password and generate distinct JWT and bootstrap keys.
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
docker compose build
docker compose up -d --wait db redis
docker compose run --rm migrate
docker compose up -d api
```

Generate secrets in your terminal and insert the values into `.env`; **do not put Python commands inside `.env`**. The file is gitignored. Compose configures the internal `db` hostname for the API.

Verify:

```bash
curl -fsS http://localhost:8000/health/live
curl -fsS http://localhost:8000/health/ready
docker compose exec -T api alembic current
```

- Swagger UI: http://localhost:8000/docs
- OpenAPI: http://localhost:8000/openapi.json
- Current Alembic head: `0003` (authentication sessions and refresh tokens)

## API endpoints

| Method | Path | Access |
| --- | --- | --- |
| GET | `/health/live`, `/health/ready` | Public (restrict exposure) |
| POST | `/api/v1/auth/register` | Bootstrap key |
| POST | `/api/v1/auth/login` | Public, rate limited |
| POST | `/api/v1/auth/refresh` | Refresh token, rate limited |
| POST | `/api/v1/auth/logout` | Access JWT with `sid` |
| GET | `/api/v1/users/me` | Authenticated |
| GET, POST | `/api/v1/users` | Organization admin |
| GET | `/api/v1/customers` | Own organization |
| POST | `/api/v1/customers` | Organization admin |
| GET | `/api/v1/customers/{customer_id}` | Own organization |
| PATCH | `/api/v1/customers/{customer_id}` | Organization admin |

Unauthorized requests return `401`; forbidden operations return `403`; a customer belonging to another organization returns `404` to avoid disclosing its existence.

## Verification

The following results were observed **locally** in Docker, not in a public deployment:

| Check | Result |
| --- | --- |
| FastAPI + PostgreSQL 17 startup | Passed |
| Liveness / readiness | HTTP 200 / HTTP 200 |
| Alembic migration `0003` | Validated against isolated PostgreSQL |
| Full local pytest suite | 50 passed (SQLite, Redis and PostgreSQL integration) |
| PostgreSQL concurrency and row locking | Passed |
| HTTP authentication checks | Login, refresh, logout, replay detection and rate limiting passed |
| Ruff lint / formatting | Passed |

**Integration tests can drop and recreate tables.** Always use a dedicated disposable test database, never the development or production database.

See [Development and testing](docs/DEVELOPMENT.md).

GitHub Actions is configured in [CI](.github/workflows/ci.yml); its results must be verified after the first push. No automatic deployment is configured.

## Known limitations and roadmap

- No PostgreSQL Row-Level Security: tenant filtering currently operates in the application.
- Logout revokes refresh credentials immediately, but existing access JWTs remain valid until expiry (30 minutes by default).
- Production deployment still requires managed TLS, trusted-proxy configuration, centralized secrets, session cleanup and complete monitoring.
- Future work: authentication hardening, audit events, observability, stronger tenant boundaries, dependency scanning and deployment runbooks.

These limitations are tracked in [Security](docs/SECURITY.md).

## Authentication sessions (v0.4.0)

- Login creates a persistent session and returns an access JWT and a refresh token.
- Access JWTs expire after 30 minutes by default; the `sid` claim identifies the session.
- Refresh tokens are stored only as SHA-256 hashes in PostgreSQL.
- Sessions expire after 14 days, without extending their original expiry on refresh.
- Each successful refresh rotates the refresh token. Reusing an already consumed token revokes the entire session.
- Logout revokes the current session's refresh credentials. Other sessions remain independent.
- Legacy access JWTs without `sid` remain accepted by existing protected endpoints, but cannot be used for session logout.
- Login, registration and refresh use separate Redis rate limits of 5, 3 and 10 requests per minute per client IP, respectively.
- Token-bearing responses include `Cache-Control: no-store` and `Pragma: no-cache`.
- Clients must serialize refresh operations to avoid accidental reuse detection.
- Apply Alembic revision `0003` before enabling the new authentication endpoints on an existing database.

For internet-facing deployment, configure trusted proxies, TLS, secrets, monitoring and expired-session cleanup. Redis unavailability causes protected authentication requests to fail closed.

## Documentation and license

- [Development and testing](docs/DEVELOPMENT.md)
- [Security model](docs/SECURITY.md)
- [Architecture decision record](docs/adr/0001-modular-monolith.md)

MIT License. See [LICENSE](LICENSE).

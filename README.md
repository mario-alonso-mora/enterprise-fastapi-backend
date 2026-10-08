# Enterprise FastAPI Backend

**Modular multi-tenant REST API built with FastAPI, PostgreSQL and SQLAlchemy 2.**

Enterprise FastAPI Backend implements the foundations of a B2B platform: organization onboarding, authentication, role-based access control (RBAC), tenant-scoped customer operations, schema migrations and automated tests.

The design prioritizes clear authorization boundaries, data integrity and reproducible development workflows.

> **Status: v0.1.0.** Functional local implementation; **not production-hardened**. Review [Security](docs/SECURITY.md) before exposing the API to the internet.

## Engineering highlights

- **Tenant isolation:** customer queries use the organization resolved from the authenticated user, not a client-provided organization ID.
- **Authentication:** Argon2id password hashing and expiring JWT bearer tokens.
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
docker compose up -d db
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
- Initial Alembic revision: `0001 (head)`

## API endpoints

| Method | Path | Access |
| --- | --- | --- |
| GET | `/health/live`, `/health/ready` | Public (restrict exposure) |
| POST | `/api/v1/auth/register` | Bootstrap key |
| POST | `/api/v1/auth/login` | Public |
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
| Alembic revision | `0001 (head)` |
| pytest with SQLite | 11 passed |
| pytest with PostgreSQL | 11 passed |
| HTTP end-to-end checks | 13 passed (JWT, tenant isolation, RBAC) |
| Ruff lint / formatting | Passed |

**Integration tests can drop and recreate tables.** Always use a dedicated disposable test database, never the development or production database.

See [Development and testing](docs/DEVELOPMENT.md).

GitHub Actions is configured in [CI](.github/workflows/ci.yml); its results must be verified after the first push. No automatic deployment is configured.

## Known limitations and roadmap

- No PostgreSQL Row-Level Security: tenant filtering currently operates in the application.
- No login rate limiting or token refresh/revocation yet.
- No managed TLS, centralized secrets, domain audit trail or complete monitoring.
- Future work: authentication hardening, audit events, observability, stronger tenant boundaries, dependency scanning and deployment runbooks.

These limitations are tracked in [Security](docs/SECURITY.md).

## Documentation and license

- [Development and testing](docs/DEVELOPMENT.md)
- [Security model](docs/SECURITY.md)
- [Architecture decision record](docs/adr/0001-modular-monolith.md)

MIT License. See [LICENSE](LICENSE).

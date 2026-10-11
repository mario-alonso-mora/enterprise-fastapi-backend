# Development and testing

All commands run from the repository root. Use Docker to reproduce the development environment.

## Service checks

```bash
docker compose config --quiet
docker compose ps
docker compose exec -T api alembic current
curl -fsS http://localhost:8000/health/live
curl -fsS http://localhost:8000/health/ready
```

## Local Ruff and SQLite tests

```bash
docker compose run --rm --no-deps --user root \
  -v "$PWD:/code" --entrypoint sh api -c '
    python -m pip install --no-cache-dir -q ".[dev]" &&
    ruff check app tests &&
    ruff format --check app tests &&
    python -m pytest -q
  '
```

## PostgreSQL and Redis integration tests

The standard pytest client fixture uses in-memory SQLite
when `TEST_DATABASE_URL` is not configured.

When `TEST_DATABASE_URL` is configured, the fixture drops
and recreates tables. Never point it at the development
database `enterprise` or any production database.

The authentication concurrency tests use a different
variable: `AUTH_TEST_ADMIN_DATABASE_URL`.

These tests create an isolated temporary PostgreSQL database,
run the concurrency checks and delete that database.
The database user must have permission to create databases.

Real Redis integration tests use `TEST_REDIS_URL`.

The full local suite was validated with SQLite,
real Redis and isolated PostgreSQL concurrency tests.

GitHub Actions uses dedicated PostgreSQL and Redis services
to reproduce the integration checks.

## Migrations and rebuilds

```bash
docker compose run --rm migrate
docker compose exec -T api alembic current
docker compose build api
docker compose up -d --force-recreate api
```

Wait for API startup before calling health endpoints. CI uses PostgreSQL 17 and runs migrations, schema-drift checks, Ruff and pytest. Validate the first GitHub Actions run after publishing.

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

## Ruff and SQLite tests

```bash
docker compose run --rm --no-deps --user root \
  -v "$PWD:/code" --entrypoint sh api -c '
    python -m pip install --no-cache-dir -q ".[dev]" &&
    ruff check app tests &&
    ruff format --check app tests &&
    python -m pytest -q
  '
```

## PostgreSQL tests

**Warning:** pytest fixtures drop and recreate application tables. Use a dedicated disposable database called `enterprise_test` — never the main `enterprise` database.

Create that database once if necessary. Then set `TEST_DATABASE_URL` to its connection URL when running pytest.

See the test fixtures in `tests/conftest.py` for exact database lifecycle behavior. Run the same tests against the dedicated PostgreSQL database before merging significant persistence changes.

## Migrations and rebuilds

```bash
docker compose run --rm migrate
docker compose exec -T api alembic current
docker compose build api
docker compose up -d --force-recreate api
```

Wait for API startup before calling health endpoints. CI uses PostgreSQL 17 and runs migrations, schema-drift checks, Ruff and pytest. Validate the first GitHub Actions run after publishing.

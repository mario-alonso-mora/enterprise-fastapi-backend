# ADR 0001 — Modular monolith with synchronous SQLAlchemy

- **Status:** Accepted
- **Date:** 2026-10-08
- **Scope:** Enterprise FastAPI Backend v0.1.0

## Context

A B2B application needs organization-aware authorization, relational integrity, schema migrations and reproducible testing. A distributed architecture would introduce operational and data-consistency complexity before there is evidence that it is needed.

## Decision

Build a **FastAPI modular monolith** with synchronous SQLAlchemy 2 sessions and PostgreSQL.

Group capabilities by feature. Use services for substantial application flows and repositories for reusable, tenant-scoped database access.

Determine customer organization from the authenticated user, not from a request parameter.

## Benefits

- Simpler deployment, transaction handling and debugging.
- Explicit responsibilities and HTTP contracts.
- RBAC and organization-scoped queries supported by database constraints.
- Clear path to workers, async I/O or independently deployable services if justified by measurements.

## Trade-offs

- Synchronous database operations consume threadpool resources; benchmark before moving workloads to async.
- PostgreSQL Row-Level Security is not implemented; a missing tenant predicate remains a security risk.
- A user currently belongs to one organization; supporting multi-organization memberships requires a new model.
- Layers are introduced pragmatically rather than uniformly in every feature.

## Alternatives

Microservices, fully asynchronous SQLAlchemy and database-enforced RLS were considered but deferred until operational, performance or threat-model requirements justify their costs.

## Review criteria

Revisit this decision when load measurements show contention, users need multiple organization memberships, or stronger tenant isolation is required.

Extend cross-tenant and role-based integration tests for every new feature.

# Transactional Audit Trail

## Overview

The audit module records customer creation and modification events.

Each event identifies the actor, organization, affected entity,
operation, changed field names, request identifier, and timestamp.

## Architecture

- FastAPI router for administrator-only event retrieval.
- SQLAlchemy AuditEvent model.
- PostgreSQL persistence through Alembic migration 0002.
- Audit writes participate in the customer transaction.
- Pagination and organization-scoped queries.

## Events

| Action | Description |
|--------|-------------|
| customer.created | A customer was created |
| customer.updated | Existing customer fields were modified |

## API

GET /api/v1/audit-events

Authentication: JWT Bearer token.

Authorization: admin role.

The endpoint returns only events belonging to the authenticated
administrator's organization.

Pagination parameters:

- limit: 1 to 100, default 20
- offset: non-negative integer, default 0

## Transactional guarantees

Customer writes and their audit events share a database transaction.

If the transaction fails before commit, neither the business change
nor the audit event persists.

Automated tests validate forced failures during customer creation
and modification against SQLite and PostgreSQL.

## Data minimization

Audit events contain changed field names, not previous or new
field values.

Passwords, access tokens, and customer field values must not
be written to audit records.

## Current limitations

- Only customer creation and modification are audited.
- Events are not cryptographically immutable.
- No retention or archival policy has been implemented.
- Database administrators retain the ability to alter stored records.
- This module is not, by itself, a regulatory-compliance solution.

## Verification

Run:

    ruff check .
    ruff format --check .
    pytest -q
    alembic check

The PostgreSQL integration suite uses the separate enterprise_test
database configured through TEST_DATABASE_URL.

See tests/test_audit.py and tests/test_audit_atomicity.py.

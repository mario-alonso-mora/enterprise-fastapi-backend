# Security model

**Scope:** v0.1.0 local development implementation. This is not a security certification.

## Implemented controls

- Bootstrap organization registration requires `X-Bootstrap-Key`.
- Passwords are stored as Argon2id hashes; access tokens are signed and expire.
- Protected routes validate JWT bearer tokens.
- `admin` and `member` roles control write permissions.
- Tenant-owned customer queries use the organization of the authenticated user.
- Cross-tenant customer reads return `404`; database constraints protect data integrity.
- Local Compose publishes the API on `127.0.0.1:8000`, not all host interfaces.

## Known risks and limitations

- Login and registration do not have rate limiting or account-abuse defenses.
- Refresh tokens, token revocation and a complete session lifecycle are not implemented.
- Tenant isolation is application-level; PostgreSQL RLS is not enabled.
- Readiness is unauthenticated and must be restricted at the network boundary.
- TLS, external secrets management, domain audit trails, backups, monitoring and incident response are not production-ready.

## Handling secrets

Do not commit `.env`, credentials, access tokens or real customer data. Use different randomly generated values for `JWT_SECRET_KEY` and `BOOTSTRAP_KEY`, and rotate exposed secrets.

PostgreSQL integration tests may **drop and recreate tables**: use only a disposable test database.

Before deploying publicly, harden authentication, enforce TLS/network policies, threat-model tenant isolation, implement monitoring/auditing/backups, and establish a tested release and rollback procedure.

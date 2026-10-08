# Known Issues

## Intermittent authentication failure in integration tests

During repeated local integration-test runs, some authenticated
requests returned an unexpected HTTP 401 immediately after a
successful login.

Observations:

- Reproduced intermittently with SQLite and PostgreSQL tests.
- The affected endpoint varied between test executions.
- Subsequent repeated runs passed without reproducing the failure.
- The root cause has not yet been identified.
- No conclusion has been established about production impact.

Required follow-up:

1. Identify the exact authentication rejection reason.
2. Investigate JWT validation, database session handling and fixtures.
3. Introduce targeted regression coverage.
4. Establish reliable repeated execution before v1.0.0.

The issue must not be considered resolved solely because
individual test suites pass.

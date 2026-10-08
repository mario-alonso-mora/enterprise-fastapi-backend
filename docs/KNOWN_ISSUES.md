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

## Investigation update — 2026-10-08

The intermittent 401 was reproduced and identified as
`jwt.exceptions.ImmatureSignatureError`.

Mitigations implemented:

- Added a five-second JWT clock-skew tolerance.
- Added regression tests for permitted clock skew, future-issued
  tokens, expired tokens, and invalid signatures.
- Restored Windows time synchronization using W32Time and NTP.
- Confirmed Windows, WSL2, and Docker clock alignment.

Validation:

- SQLite: 200 passing tests across 10 complete runs.
- PostgreSQL: 200 passing tests across 10 complete runs.
- No unexpected 401 responses in this validation.

Security note:

The five-second leeway also extends expiration acceptance
by up to five seconds.

Remaining uncertainty:

The direct JWT rejection reason was established, but the
underlying cause of the intermittent clock discrepancy has
not been conclusively proven. Continue monitoring and
investigate if the rejection reappears.

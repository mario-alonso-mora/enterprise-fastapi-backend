"""Verify customer changes and audit events share one transaction."""

from importlib import import_module

import pytest


def inject_audit_failure(monkeypatch):
    """Flush business and audit writes, then force a failure."""
    module = import_module("app.modules.customers.router")
    original_record_event = module.record_event

    def failing_record_event(db, **kwargs):
        original_record_event(db, **kwargs)

        # Both business changes and the audit event reach the DB
        # inside the current transaction, without committing.
        db.flush()

        raise RuntimeError("forced audit transaction failure")

    monkeypatch.setattr(module, "record_event", failing_record_event)


def test_customer_creation_rolls_back_with_audit_failure(client, register, login, monkeypatch):
    response = register("acme", "owner@acme.example.com")
    assert response.status_code == 201

    admin = login("owner@acme.example.com")
    inject_audit_failure(monkeypatch)

    with pytest.raises(RuntimeError, match="forced audit transaction failure"):
        client.post(
            "/api/v1/customers",
            json={
                "external_ref": "ROLLBACK-001",
                "name": "Must not persist",
            },
            headers=admin,
        )

    customers = client.get("/api/v1/customers", headers=admin)
    assert customers.status_code == 200
    assert customers.json()["total"] == 0

    audit = client.get("/api/v1/audit-events", headers=admin)
    assert audit.status_code == 200
    assert audit.json()["total"] == 0


def test_customer_update_rolls_back_with_audit_failure(client, register, login, monkeypatch):
    response = register("acme", "owner@acme.example.com")
    assert response.status_code == 201

    admin = login("owner@acme.example.com")

    created = client.post(
        "/api/v1/customers",
        json={
            "external_ref": "ROLLBACK-002",
            "name": "Original name",
        },
        headers=admin,
    )

    assert created.status_code == 201
    customer_id = created.json()["id"]

    inject_audit_failure(monkeypatch)

    with pytest.raises(RuntimeError, match="forced audit transaction failure"):
        client.patch(
            f"/api/v1/customers/{customer_id}",
            json={"name": "Must not persist"},
            headers=admin,
        )

    customer = client.get(
        f"/api/v1/customers/{customer_id}",
        headers=admin,
    )
    assert customer.status_code == 200
    assert customer.json()["name"] == "Original name"

    audit = client.get("/api/v1/audit-events", headers=admin)
    assert audit.status_code == 200
    assert audit.json()["total"] == 1
    assert audit.json()["items"][0]["action"] == "customer.created"

"""Integration tests for customer audit events."""


def events(client, headers):
    response = client.get(
        "/api/v1/audit-events",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_audit_create_and_update(client, register, login):
    assert register("acme", "owner@acme.example.com").status_code == 201
    admin = login("owner@acme.example.com")

    actor = client.get("/api/v1/users/me", headers=admin).json()["id"]

    assert events(client, admin)["total"] == 0

    created = client.post(
        "/api/v1/customers",
        json={
            "external_ref": "AUD-001",
            "name": "Alice",
            "email": "alice@example.com",
        },
        headers=admin,
    )
    assert created.status_code == 201, created.text

    customer_id = created.json()["id"]
    audit = events(client, admin)

    assert audit["total"] == 1
    event = audit["items"][0]
    assert event["action"] == "customer.created"
    assert event["entity_id"] == customer_id
    assert event["actor_id"] == actor
    assert event["request_id"] == created.headers["X-Request-ID"]
    assert "alice@example.com" not in str(audit)

    updated = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"name": "Alice updated"},
        headers=admin,
    )
    assert updated.status_code == 200, updated.text

    audit = events(client, admin)
    assert audit["total"] == 2

    update_event = next(e for e in audit["items"] if e["action"] == "customer.updated")
    assert update_event["changed_fields"] == ["name"]
    assert update_event["request_id"] == updated.headers["X-Request-ID"]
    assert "Alice updated" not in str(audit)

    no_changes = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={},
        headers=admin,
    )
    assert no_changes.status_code == 200
    assert events(client, admin)["total"] == 2


def test_failed_operations_do_not_create_events(client, register, login):
    assert register("acme", "owner@acme.example.com").status_code == 201
    admin = login("owner@acme.example.com")

    created = client.post(
        "/api/v1/customers",
        json={"external_ref": "DUP-001", "name": "Original"},
        headers=admin,
    )
    assert created.status_code == 201
    customer_id = created.json()["id"]

    duplicate = client.post(
        "/api/v1/customers",
        json={"external_ref": "DUP-001", "name": "Duplicate"},
        headers=admin,
    )
    assert duplicate.status_code == 409

    invalid = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"name": None},
        headers=admin,
    )
    assert invalid.status_code == 422

    assert events(client, admin)["total"] == 1
    customers = client.get("/api/v1/customers", headers=admin)
    assert customers.json()["total"] == 1


def test_audit_tenant_isolation_and_permissions(client, register, login):
    assert register("acme", "owner@acme.example.com").status_code == 201
    assert register("globex", "owner@globex.example.com").status_code == 201

    admin_a = login("owner@acme.example.com")
    admin_b = login("owner@globex.example.com")

    created = client.post(
        "/api/v1/customers",
        json={"external_ref": "TEN-001", "name": "Acme only"},
        headers=admin_a,
    )
    assert created.status_code == 201

    assert events(client, admin_a)["total"] == 1
    assert events(client, admin_b)["total"] == 0

    unauthenticated = client.get("/api/v1/audit-events")
    assert unauthenticated.status_code == 401

    member = client.post(
        "/api/v1/users",
        json={
            "email": "member@acme.example.com",
            "password": "MemberPassword1234",
            "role": "member",
        },
        headers=admin_a,
    )
    assert member.status_code == 201

    member_auth = login(
        "member@acme.example.com",
        "MemberPassword1234",
    )

    forbidden = client.get(
        "/api/v1/audit-events",
        headers=member_auth,
    )
    assert forbidden.status_code == 403

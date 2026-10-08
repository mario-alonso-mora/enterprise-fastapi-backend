def test_tenant_isolation_and_unique_reference(client, register, login):
    assert register("acme", "owner@acme.example.com").status_code == 201
    assert register("globex", "owner@globex.example.com").status_code == 201
    acme = login("owner@acme.example.com")
    globex = login("owner@globex.example.com")

    created = client.post(
        "/api/v1/customers",
        json={"external_ref": "C-001", "name": "Alice", "email": "alice@example.com"},
        headers=acme,
    )
    assert created.status_code == 201, created.text
    customer_id = created.json()["id"]
    assert (
        client.post(
            "/api/v1/customers",
            json={"external_ref": "C-001", "name": "Alice Duplicate"},
            headers=acme,
        ).status_code
        == 409
    )

    # The same reference is valid in a DIFFERENT organization.
    globex_created = client.post(
        "/api/v1/customers",
        json={"external_ref": "C-001", "name": "Globex Customer"},
        headers=globex,
    )
    assert globex_created.status_code == 201
    assert client.get(f"/api/v1/customers/{customer_id}", headers=globex).status_code == 404
    assert (
        client.patch(
            f"/api/v1/customers/{customer_id}", json={"name": "Hacked"}, headers=globex
        ).status_code
        == 404
    )

    acme_list = client.get("/api/v1/customers", headers=acme).json()
    globex_list = client.get("/api/v1/customers", headers=globex).json()
    assert acme_list["total"] == 1
    assert globex_list["total"] == 1
    assert acme_list["items"][0]["id"] != globex_list["items"][0]["id"]
    assert client.get("/api/v1/customers?q=Alice", headers=acme).json()["total"] == 1


def test_member_can_read_but_cannot_write(client, register, login):
    register("acme", "admin@acme.example.com")
    admin = login("admin@acme.example.com")
    member_create = client.post(
        "/api/v1/users",
        json={
            "email": "member@acme.example.com",
            "password": "MemberPassword1234",
            "role": "member",
        },
        headers=admin,
    )
    assert member_create.status_code == 201, member_create.text
    member = login("member@acme.example.com", "MemberPassword1234")
    assert client.get("/api/v1/users/me", headers=member).status_code == 200
    assert client.get("/api/v1/customers", headers=member).status_code == 200
    assert (
        client.post(
            "/api/v1/customers", json={"external_ref": "A01", "name": "Forbidden"}, headers=member
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/users",
            json={"email": "unknown@acme.example.com", "password": "MemberPassword1234"},
            headers=member,
        ).status_code
        == 403
    )

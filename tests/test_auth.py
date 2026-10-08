def test_bootstrap_key_required(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Acme Ltd",
            "organization_slug": "acme",
            "admin_email": "owner@acme.example.com",
            "admin_password": "StrongPassword-12345",
        },
    )
    assert response.status_code == 401


def test_registration_login_and_me(client, register, login):
    response = register("acme", "owner@acme.example.com")
    assert response.status_code == 201, response.text
    assert response.json()["organization_id"]
    assert register("acme", "different@acme.example.com").status_code == 409
    assert register("other", "owner@acme.example.com").status_code == 409
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "owner@acme.example.com", "password": "bad-password"},
        ).status_code
        == 401
    )
    header = login("owner@acme.example.com")
    me = client.get("/api/v1/users/me", headers=header)
    assert me.status_code == 200
    assert me.json()["role"] == "admin"
    assert "password_hash" not in me.text


def test_bad_bootstrap_key(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Acme Ltd",
            "organization_slug": "acme",
            "admin_email": "owner@acme.example.com",
            "admin_password": "StrongPassword-12345",
        },
        headers={"X-Bootstrap-Key": "wrong"},
    )
    assert response.status_code == 401


def test_invalid_token_rejected(client):
    assert (
        client.get("/api/v1/users/me", headers={"Authorization": "Bearer bogus"}).status_code == 401
    )

from app.core.config import get_settings


def test_registration_validation(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Org",
            "organization_slug": "Invalid Spaces",
            "admin_email": "not-an-email",
            "admin_password": "too-short",
        },
        headers={"X-Bootstrap-Key": get_settings().bootstrap_key.get_secret_value()},
    )
    assert response.status_code == 422


def test_customer_pagination_and_patch(client, register, login):
    register("acme", "admin@acme.example.com")
    headers = login("admin@acme.example.com")
    for ref in ("A01", "A02", "A03"):
        response = client.post(
            "/api/v1/customers",
            json={"external_ref": ref, "name": "Customer " + ref},
            headers=headers,
        )
        assert response.status_code == 201
    result = client.get("/api/v1/customers?limit=2&offset=0", headers=headers)
    assert result.status_code == 200
    assert result.json()["total"] == 3
    assert len(result.json()["items"]) == 2
    item_id = result.json()["items"][0]["id"]
    patched = client.patch(
        f"/api/v1/customers/{item_id}", json={"name": "Changed"}, headers=headers
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Changed"
    assert (
        client.patch(
            f"/api/v1/customers/{item_id}", json={"name": None}, headers=headers
        ).status_code
        == 422
    )

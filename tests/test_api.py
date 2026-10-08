def test_liveness_and_request_id(client):
    result = client.get("/health/live")
    assert result.status_code == 200
    assert result.json() == {"status": "ok"}
    assert result.headers.get("x-request-id")


def test_readiness(client):
    result = client.get("/health/ready")
    assert result.status_code == 200
    assert result.json() == {"status": "ready"}


def test_openapi_and_anonymous_rejected(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/customers" in paths
    assert client.get("/api/v1/customers").status_code == 401
    assert client.get("/api/v1/users/me").status_code == 401

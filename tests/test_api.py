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


def test_request_correlation_and_structured_logging(client, caplog):
    import json
    import logging
    from uuid import UUID

    with caplog.at_level(logging.INFO, logger="enterprise.requests"):
        first = client.get("/health/live?secret=must-not-be-logged")
        second = client.get("/health/live")

    assert first.status_code == 200
    assert second.status_code == 200

    first_id = first.headers["X-Request-ID"]
    second_id = second.headers["X-Request-ID"]

    assert UUID(first_id).version == 4
    assert UUID(second_id).version == 4
    assert first_id != second_id

    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "enterprise.requests"
    ]

    for request_id in (first_id, second_id):
        matching = [event for event in events if event["request_id"] == request_id]
        assert len(matching) == 1

        event = matching[0]
        assert event["event"] == "http_request"
        assert event["level"] == "INFO"
        assert event["timestamp"]
        assert event["method"] == "GET"
        assert event["path"] == "/health/live"
        assert event["status_code"] == 200
        assert event["duration_ms"] >= 0

    assert "must-not-be-logged" not in json.dumps(events)


def test_openapi_version_matches_installed_package(client):
    from importlib.metadata import version

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["version"] == version("enterprise-fastapi-starter")


def test_unhandled_error_is_safe_and_correlated(client, caplog):
    import json
    import logging
    from uuid import UUID

    def failing_endpoint():
        raise RuntimeError("SENSITIVE_VALUE_MUST_NOT_LEAK")

    client.app.add_api_route(
        "/__test__/unexpected-error",
        failing_endpoint,
        methods=["GET"],
        include_in_schema=False,
    )

    with caplog.at_level(logging.INFO, logger="enterprise.requests"):
        response = client.get("/__test__/unexpected-error?password=private-query-value")

    assert response.status_code == 500

    request_id = response.headers["X-Request-ID"]
    assert UUID(request_id).version == 4

    assert response.json() == {
        "detail": "Internal server error",
        "request_id": request_id,
    }

    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "enterprise.requests"
    ]

    error_events = [
        event
        for event in events
        if event["event"] == "unhandled_exception" and event["request_id"] == request_id
    ]
    assert len(error_events) == 1
    assert error_events[0]["error_type"] == "RuntimeError"

    request_events = [
        event
        for event in events
        if event["event"] == "http_request" and event["request_id"] == request_id
    ]
    assert len(request_events) == 1
    assert request_events[0]["status_code"] == 500
    assert request_events[0]["level"] == "ERROR"

    output = json.dumps(events) + response.text
    assert "SENSITIVE_VALUE_MUST_NOT_LEAK" not in output
    assert "private-query-value" not in output


def test_handled_auth_error_keeps_request_id(client):
    from uuid import UUID

    response = client.get("/api/v1/users/me")

    assert response.status_code == 401
    assert UUID(response.headers["X-Request-ID"]).version == 4


def test_metrics_are_protected_and_do_not_leak_urls(client, register, login):
    from secrets import token_urlsafe
    from types import SimpleNamespace

    from pydantic import SecretStr

    from app.core.config import get_settings

    registration = register("metrics-admin", "metrics-admin@example.com")
    assert registration.status_code == 201

    admin_headers = login("metrics-admin@example.com")
    metrics_token = token_urlsafe(32)

    previous_override = client.app.dependency_overrides.get(get_settings)

    try:
        client.app.dependency_overrides[get_settings] = lambda: SimpleNamespace(
            metrics_scrape_token=None
        )

        assert client.get("/internal/metrics").status_code == 404

        client.app.dependency_overrides[get_settings] = lambda: SimpleNamespace(
            metrics_scrape_token=SecretStr(metrics_token)
        )

        assert client.get("/internal/metrics").status_code == 401
        assert client.get("/internal/metrics", headers=admin_headers).status_code == 401
        assert (
            client.get(
                "/internal/metrics",
                headers={"Authorization": "Bearer invalid-token"},
            ).status_code
            == 401
        )

        assert client.get("/health/live?secret=private-value").status_code == 200
        assert client.get("/missing/private-identifier").status_code == 404

        response = client.get(
            "/internal/metrics",
            headers={"Authorization": f"Bearer {metrics_token}"},
        )

        assert response.status_code == 200
        assert "enterprise_http_requests_total" in response.text
        assert "enterprise_http_request_duration_seconds" in response.text
        assert 'route="/health/live"' in response.text
        assert 'route="/unmatched"' in response.text

        assert "private-value" not in response.text
        assert "private-identifier" not in response.text
        assert "metrics-admin@example.com" not in response.text
        assert metrics_token not in response.text

    finally:
        if previous_override is None:
            client.app.dependency_overrides.pop(get_settings, None)
        else:
            client.app.dependency_overrides[get_settings] = previous_override

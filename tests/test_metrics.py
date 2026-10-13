from prometheus_client import generate_latest

from app.core.metrics import HTTPMetrics


def test_unknown_http_methods_use_bounded_label():
    metrics = HTTPMetrics()

    metrics.observe(
        method="CUSTOM-SENSITIVE-123",
        route="/api/v1/users/{user_id}",
        status_code=405,
        duration_seconds=0.01,
    )

    output = generate_latest(metrics.registry).decode()

    assert 'method="OTHER"' in output
    assert 'route="/api/v1/users/{user_id}"' in output
    assert "CUSTOM-SENSITIVE-123" not in output
    assert "enterprise_http_requests_total" in output
    assert "enterprise_http_request_duration_seconds" in output

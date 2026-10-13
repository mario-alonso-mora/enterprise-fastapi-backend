"""HTTP metrics with bounded route labels."""

from prometheus_client import CollectorRegistry, Counter, Histogram

ALLOWED_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})


def route_template(scope: dict) -> str:
    """Avoid raw URLs and unbounded labels."""
    route = getattr(scope.get("route"), "path", None)
    return route if isinstance(route, str) else "/unmatched"


class HTTPMetrics:
    def __init__(self):
        self.registry = CollectorRegistry()

        self.requests = Counter(
            "enterprise_http_requests_total",
            "Total HTTP requests",
            ["method", "route", "status_code"],
            registry=self.registry,
        )

        self.duration = Histogram(
            "enterprise_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "route"],
            buckets=(
                0.005,
                0.01,
                0.025,
                0.05,
                0.1,
                0.25,
                0.5,
                1,
                2.5,
                5,
                10,
            ),
            registry=self.registry,
        )

    def observe(
        self,
        method: str,
        route: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        method = method if method in ALLOWED_METHODS else "OTHER"

        self.requests.labels(
            method=method,
            route=route,
            status_code=str(status_code),
        ).inc()

        self.duration.labels(
            method=method,
            route=route,
        ).observe(duration_seconds)

import json
import logging
import time
import uuid
from datetime import UTC, datetime
from hmac import compare_digest
from importlib.metadata import version

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.router import router as v1_router
from app.core.config import Settings, get_settings
from app.core.metrics import HTTPMetrics, route_template
from app.db.session import get_db

logger = logging.getLogger("enterprise.requests")
logging.basicConfig(level=logging.INFO, format="%(message)s")


_metrics_bearer = HTTPBearer(auto_error=False)


def require_metrics_scraper(
    credentials: HTTPAuthorizationCredentials | None = Depends(_metrics_bearer),
    settings: Settings = Depends(get_settings),
) -> None:
    configured = settings.metrics_scrape_token

    if configured is None or not configured.get_secret_value():
        raise HTTPException(status_code=404, detail="Not Found")

    if credentials is None or not compare_digest(
        credentials.credentials,
        configured.get_secret_value(),
    ):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )


def create_app() -> FastAPI:
    app = FastAPI(title=get_settings().app_name, version=version("enterprise-fastapi-starter"))
    metrics = HTTPMetrics()

    @app.middleware("http")
    async def request_log(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code

        except Exception as exc:
            logger.error(
                json.dumps(
                    {
                        "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
                        "level": "ERROR",
                        "event": "unhandled_exception",
                        "request_id": request_id,
                        "error_type": type(exc).__name__,
                    }
                )
            )

            response = JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "request_id": request_id,
                },
            )

        finally:
            duration_seconds = time.perf_counter() - start
            route = route_template(request.scope)
            metrics.observe(request.method, route, status_code, duration_seconds)
            if status_code >= 500:
                log_level = logging.ERROR
            elif status_code >= 400:
                log_level = logging.WARNING
            else:
                log_level = logging.INFO

            logger.log(
                log_level,
                json.dumps(
                    {
                        "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
                        "level": logging.getLevelName(log_level),
                        "event": "http_request",
                        "request_id": request_id,
                        "method": request.method,
                        "path": route,
                        "status_code": status_code,
                        "duration_ms": round(duration_seconds * 1000, 2),
                    }
                ),
            )

        response.headers["X-Request-ID"] = request_id
        return response

    @app.get(
        "/internal/metrics",
        include_in_schema=False,
        dependencies=[Depends(require_metrics_scraper)],
    )
    def metrics_endpoint() -> Response:
        return Response(
            content=generate_latest(metrics.registry),
            media_type=CONTENT_TYPE_LATEST,
        )

    @app.get("/health/live", tags=["Health"])
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["Health"])
    def ready(db: Session = Depends(get_db)) -> dict[str, str]:
        try:
            db.execute(text("SELECT 1"))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Database unavailable") from exc
        return {"status": "ready"}

    app.include_router(v1_router)
    return app


app = create_app()

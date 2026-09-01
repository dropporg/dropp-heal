import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# These describe Heal itself. Monitored-target latency lives in InfluxDB and is
# deliberately not exposed here.
CHECKS_TOTAL = Counter("heal_checks_total", "Checks executed", ["probe_type"])
CHECKS_SUCCESS_TOTAL = Counter(
    "heal_checks_success_total", "Checks that succeeded", ["probe_type"]
)
CHECKS_FAILED_TOTAL = Counter(
    "heal_checks_failed_total", "Checks that failed", ["probe_type"]
)
CHECK_DURATION = Histogram(
    "heal_check_duration_seconds", "Time to run one site's probes", ["probe_type"]
)
ACTIVE_TARGETS = Gauge(
    "heal_active_targets", "Sites currently scheduled for monitoring"
)
RUNNING_CHECKS = Gauge("heal_worker_running_checks", "Checks executing right now")
HTTP_REQUESTS_TOTAL = Counter(
    "heal_http_requests_total", "API requests", ["method", "path", "status"]
)
HTTP_REQUEST_DURATION = Histogram(
    "heal_http_request_duration_seconds", "API request duration", ["method", "path"]
)


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def register_metrics_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def track_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Route templates keep label cardinality bounded; raw paths would not.
        started = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        if path != "/metrics":
            HTTP_REQUESTS_TOTAL.labels(request.method, path, response.status_code).inc()
            HTTP_REQUEST_DURATION.labels(request.method, path).observe(
                time.perf_counter() - started
            )
        return response

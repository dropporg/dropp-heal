from fastapi import APIRouter, Response

from api.observability import metrics_response

router = APIRouter(tags=["observability"])


@router.get(
    "/metrics", summary="Prometheus metrics about Heal itself", include_in_schema=True
)
async def metrics() -> Response:
    """Expose Heal's own counters, not the monitored targets' latency."""
    return metrics_response()

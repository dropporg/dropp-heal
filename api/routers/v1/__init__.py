from fastapi import APIRouter

from api.routers.v1 import metrics, sites

router = APIRouter(prefix="/api/v1")
router.include_router(sites.router)
router.include_router(metrics.router)

__all__ = ["router"]

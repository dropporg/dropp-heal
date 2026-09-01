from fastapi import APIRouter

from api.routers import observability, probe
from api.routers.v1 import router as v1_router

# Health and metrics endpoints, served by every component.
infra_router = APIRouter()
infra_router.include_router(probe.router)
infra_router.include_router(observability.router)

# The full REST API, served by the api component.
router = APIRouter()
router.include_router(infra_router)
router.include_router(v1_router)

__all__ = ["infra_router", "router"]

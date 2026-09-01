import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import __version__
from api.bootstrap import connect_datastores, disconnect_datastores, prepare
from api.config import Settings
from api.observability import register_metrics_middleware
from api.routers import router as api_router
from api.utils.errors import register_error_handlers

logger = logging.getLogger("heal.api")

SERVICE = "api"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger.info("api starting", extra={"version": __version__})
    connect_datastores(settings)
    yield
    await disconnect_datastores()
    logger.info("api stopped")


def create_app() -> FastAPI:
    """The REST API service.

    Stateless: it serves requests and never schedules checks, so replicas scale
    freely without coordinating with each other.
    """
    settings = prepare(SERVICE)

    app = FastAPI(
        title="Heal API",
        description="Network monitoring for FQDN availability, latency, and filtering detection.",
        version=__version__,
        debug=settings.debug,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.redoc_enabled else None,
        lifespan=lifespan,
    )
    app.state.settings = settings

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials="*" not in settings.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_metrics_middleware(app)
    register_error_handlers(app)
    app.include_router(api_router)
    return app

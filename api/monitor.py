import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api import __version__
from api.bootstrap import connect_datastores, disconnect_datastores, prepare
from api.config import Settings
from api.observability import register_metrics_middleware
from api.routers import infra_router
from api.tasks import Scheduler
from api.utils.errors import register_error_handlers

logger = logging.getLogger("heal.monitor")

SERVICE = "worker"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger.info(
        "worker starting",
        extra={"version": __version__, "worker_id": settings.worker_id},
    )
    connect_datastores(settings)

    scheduler = Scheduler(settings)
    app.state.scheduler = scheduler
    scheduler.start()

    yield

    # SIGTERM lands here: stop claiming, drain in-flight checks and release
    # their leases, then flush pending InfluxDB writes.
    await scheduler.stop(timeout=settings.shutdown_timeout)
    await disconnect_datastores()
    logger.info("worker stopped")


def create_app() -> FastAPI:
    """The monitoring engine service.

    Runs the scheduler and probes. It serves no REST API, only the health and
    metrics endpoints Kubernetes and Prometheus need, so the container can be
    probed and scraped like any other workload.
    """
    settings = prepare(SERVICE)

    app = FastAPI(
        title="Heal Worker",
        description="Monitoring engine: claims due sites, probes them, stores metrics.",
        version=__version__,
        debug=settings.debug,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings

    register_metrics_middleware(app)
    register_error_handlers(app)
    app.include_router(infra_router)
    return app

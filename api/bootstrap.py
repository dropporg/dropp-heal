import logging

import sentry_sdk

from api import __version__
from api.config import Settings, get_settings
from api.db import database
from api.tsdb import influxdb
from api.utils.logging import configure_logging

logger = logging.getLogger("heal")


def prepare(service: str) -> Settings:
    """Shared start-up for every component: settings, logging, error reporting."""
    settings = get_settings()
    configure_logging(settings.log_level, structured=settings.log_json)
    configure_sentry(settings, service)
    return settings


def configure_sentry(settings: Settings, service: str) -> None:
    if not settings.sentry_dsn:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(),
        environment=settings.environment,
        release=__version__,
        traces_sample_rate=settings.sentry_traces_sample_rate,
    )
    sentry_sdk.set_tag("service", service)
    logger.info("sentry enabled", extra={"service": service})


def connect_datastores(settings: Settings) -> None:
    database.connect(settings)
    influxdb.connect(settings)


async def disconnect_datastores() -> None:
    await influxdb.disconnect()
    await database.disconnect()

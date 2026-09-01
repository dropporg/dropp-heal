import logging
from typing import Any

from influxdb_client import Point
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

from api.config import Settings, get_settings

logger = logging.getLogger("heal.tsdb")


class InfluxDB:
    """Async InfluxDB connector for probe measurements.

    Historical latency lives here, never in MySQL. Targets are identified by
    their influxdb_tag, so keep tag values low-cardinality.
    """

    def __init__(self) -> None:
        self._client: InfluxDBClientAsync | None = None
        self._settings: Settings | None = None

    def connect(self, settings: Settings | None = None) -> None:
        if self._client is not None:
            return
        self._settings = settings or get_settings()
        self._client = InfluxDBClientAsync(
            url=self._settings.influxdb_url,
            token=self._settings.influxdb_token.get_secret_value(),
            org=self._settings.influxdb_org,
        )
        logger.info(
            "influxdb connector ready",
            extra={
                "url": self._settings.influxdb_url,
                "bucket": self._settings.influxdb_bucket,
            },
        )

    async def disconnect(self) -> None:
        if self._client is None:
            return
        await self._client.close()
        self._client = None
        logger.info("influxdb connector closed")

    @property
    def client(self) -> InfluxDBClientAsync:
        if self._client is None:
            raise RuntimeError("InfluxDB.connect() has not been called.")
        return self._client

    @property
    def bucket(self) -> str:
        if self._settings is None:
            raise RuntimeError("InfluxDB.connect() has not been called.")
        return self._settings.influxdb_bucket

    async def write(
        self, record: Point | list[Point], bucket: str | None = None
    ) -> None:
        """Write one or more points to the configured bucket."""
        await self.client.write_api().write(bucket=bucket or self.bucket, record=record)

    async def query(self, flux: str) -> list[Any]:
        """Run a Flux query and return its tables."""
        return await self.client.query_api().query(flux)

    async def ping(self) -> bool:
        """Report whether InfluxDB is reachable."""
        try:
            return await self.client.ping()
        except Exception:
            logger.warning("influxdb ping failed", exc_info=True)
            return False


influxdb = InfluxDB()

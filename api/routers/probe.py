from fastapi import APIRouter

from api.db import database
from api.tsdb import influxdb
from api.utils.jsonify import DATABASE_ERROR, OK, Jsonify

router = APIRouter(prefix="/probe", tags=["probe"])


@router.get("/live", summary="Liveness probe")
async def live() -> dict[str, str]:
    """Report that the process is alive. Never touches MySQL or InfluxDB."""
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe")
async def ready() -> Jsonify:
    """Report whether Heal can serve requests, checking both datastores."""
    mysql = await database.ping()
    influx = await influxdb.ping()
    healthy = mysql and influx
    return Jsonify(
        result={
            "status": "ready" if healthy else "not ready",
            "mysql": "ok" if mysql else "error",
            "influxdb": "ok" if influx else "error",
        },
        code=OK if healthy else DATABASE_ERROR,
    )

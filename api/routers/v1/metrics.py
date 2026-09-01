from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Query

from api.cruds import sites as crud
from api.dependencies import SessionDep
from api.models import ProbeType
from api.schemas.v1 import (
    MetricPoint,
    MetricSeries,
    MetricsRead,
    ProbeSnapshot,
    SiteStatusRead,
)
from api.tsdb import influxdb
from api.tsdb.queries import (
    Aggregation,
    InvalidQueryError,
    build_latest_query,
    build_metrics_query,
)
from api.utils.jsonify import INVALID_SCHEMA, NOT_FOUND, Jsonify

router = APIRouter(prefix="/sites", tags=["metrics"])


@router.get("/{site_id}/status", summary="Current state and latest probe readings")
async def site_status(site_id: UUID, session: SessionDep) -> Jsonify:
    """Latest calculated state plus the most recent reading per probe."""
    site = await crud.get(session, site_id)
    if site is None:
        return Jsonify(code=NOT_FOUND, metadata=str(site_id))

    snapshots: dict[str, ProbeSnapshot] = {}
    try:
        tables = await influxdb.query(
            build_latest_query(bucket=influxdb.bucket, target_id=site.id)
        )
    except Exception:
        tables = []

    readings: dict[str, dict] = defaultdict(dict)
    for table in tables:
        for record in table.records:
            readings[record["probe_type"]][record["_field"]] = record["_value"]
            readings[record["probe_type"]]["_time"] = record["_time"]

    for probe_type, values in readings.items():
        snapshots[probe_type] = ProbeSnapshot(
            success=bool(values.get("success")) if "success" in values else None,
            latency_ms=values.get("latency_ms"),
            status_code=(
                int(values["http_status_code"])
                if "http_status_code" in values
                else None
            ),
            packet_loss_percent=values.get("packet_loss_percent"),
            checked_at=values.get("_time"),
        )

    return Jsonify(
        result=SiteStatusRead(
            site_id=site.id,
            fqdn=site.fqdn,
            status=site.last_status,
            last_checked_at=site.last_checked_at,
            probes=snapshots,
        )
    )


@router.get("/{site_id}/metrics", summary="Historical metrics for graphing")
async def site_metrics(
    site_id: UUID,
    session: SessionDep,
    start: str = Query(
        "-1h", description="Duration such as -2d, or an RFC 3339 timestamp."
    ),
    end: str = Query("now()", description="Duration, RFC 3339 timestamp, or now()."),
    probe_type: ProbeType | None = Query(None),
    field: str | None = Query(
        None, description="Restrict to one metric, e.g. latency_ms."
    ),
    aggregation: Aggregation = Query(Aggregation.RAW),
    window: str = Query(
        "5m", description="Bucket size when aggregating, e.g. 5m or 1h."
    ),
) -> Jsonify:
    """Return one series per probe and field, ready to plot.

    Points come back sorted by time so a chart can consume them directly.
    """
    site = await crud.get(session, site_id)
    if site is None:
        return Jsonify(code=NOT_FOUND, metadata=str(site_id))

    try:
        flux = build_metrics_query(
            bucket=influxdb.bucket,
            target_id=site.id,
            start=start,
            end=end,
            probe_type=probe_type,
            field=field,
            aggregation=aggregation,
            window=window,
        )
    except InvalidQueryError as exc:
        return Jsonify(code=INVALID_SCHEMA, metadata=str(exc))

    tables = await influxdb.query(flux)
    grouped: dict[tuple[str, str], list[MetricPoint]] = defaultdict(list)
    for table in tables:
        for record in table.records:
            value = record["_value"]
            grouped[(record["probe_type"], record["_field"])].append(
                MetricPoint(
                    time=record["_time"],
                    value=(
                        float(value) if isinstance(value, (int, float, bool)) else None
                    ),
                )
            )

    series = [
        MetricSeries(probe_type=ProbeType(probe), field=name, points=points)
        for (probe, name), points in sorted(grouped.items())
    ]
    return Jsonify(
        result=MetricsRead(
            site_id=site.id,
            fqdn=site.fqdn,
            start=start,
            end=end,
            aggregation=aggregation,
            window=None if aggregation is Aggregation.RAW else window,
            series=series,
        ),
        metadata=f"{len(series)} series",
    )

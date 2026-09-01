from datetime import UTC, datetime

from influxdb_client import Point

from api.probes import ProbeResult

MEASUREMENT = "probe"


def to_point(
    result: ProbeResult,
    *,
    target_id: str,
    fqdn: str,
    influxdb_tag: str,
    status: str,
    timestamp: datetime | None = None,
) -> Point:
    """Build the InfluxDB point for one probe result.

    Tags stay low-cardinality on purpose: identifiers and enum values only,
    never latencies or error strings.
    """
    point = (
        Point(MEASUREMENT)
        .tag("target_id", target_id)
        .tag("influxdb_tag", influxdb_tag)
        .tag("fqdn", fqdn)
        .tag("probe_type", str(result.probe_type))
        .tag("status", status)
        .time(timestamp or datetime.now(UTC))
    )
    for name, value in result.metric_fields().items():
        point = point.field(name, value)
    return point

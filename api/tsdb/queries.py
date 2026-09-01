import re
from enum import StrEnum
from uuid import UUID

from api.models import ProbeType

# Flux has no bound parameters, so every interpolated value is validated
# against these patterns first. Never interpolate an unvalidated string.
DURATION_PATTERN = re.compile(r"^-?\d+(ns|us|ms|s|m|h|d|w|mo|y)$")
RFC3339_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)

MEASUREMENT = "probe"
BOOLEAN_FIELDS = frozenset({"success", "timeout"})
NUMERIC_FIELDS = (
    "latency_ms",
    "dns_latency_ms",
    "tcp_latency_ms",
    "tls_latency_ms",
    "ttfb_ms",
    "total_latency_ms",
    "packet_loss_percent",
    "http_status_code",
)

QUANTILES = {"p50": 0.5, "p95": 0.95, "p99": 0.99}


class Aggregation(StrEnum):
    RAW = "raw"
    MEAN = "mean"
    MIN = "min"
    MAX = "max"
    P50 = "p50"
    P95 = "p95"
    P99 = "p99"


class InvalidQueryError(ValueError):
    """Raised when a caller supplies a time, window, or field Flux cannot take."""


def validate_time(value: str, name: str) -> str:
    """Accept a relative duration (-2d) or an RFC 3339 timestamp."""
    value = value.strip()
    if DURATION_PATTERN.match(value):
        return value
    if RFC3339_PATTERN.match(value):
        return value.replace(" ", "T")
    raise InvalidQueryError(
        f"{name} must be a duration such as -2d or an RFC 3339 timestamp, got {value!r}"
    )


def validate_window(value: str) -> str:
    value = value.strip()
    if not DURATION_PATTERN.match(value) or value.startswith("-"):
        raise InvalidQueryError(
            f"window must be a positive duration such as 5m, got {value!r}"
        )
    return value


def validate_field(value: str) -> str:
    if value not in NUMERIC_FIELDS and value not in BOOLEAN_FIELDS:
        raise InvalidQueryError(f"unknown field {value!r}")
    return value


def build_metrics_query(
    *,
    bucket: str,
    target_id: UUID,
    start: str = "-1h",
    end: str = "now()",
    probe_type: ProbeType | None = None,
    field: str | None = None,
    aggregation: Aggregation = Aggregation.RAW,
    window: str = "5m",
) -> str:
    """Build the Flux query backing GET /sites/{id}/metrics."""
    start = validate_time(start, "start")
    stop = (
        "now()"
        if end in ("now()", "now")
        else f'time(v: "{validate_time(end, "end")}")'
    )
    start_expr = start if start.startswith("-") else f'time(v: "{start}")'

    lines = [
        f'from(bucket: "{bucket}")',
        f"  |> range(start: {start_expr}, stop: {stop})",
        f'  |> filter(fn: (r) => r._measurement == "{MEASUREMENT}")',
        f'  |> filter(fn: (r) => r.target_id == "{target_id}")',
    ]
    if probe_type is not None:
        lines.append(
            f'  |> filter(fn: (r) => r.probe_type == "{ProbeType(probe_type)}")'
        )
    if field is not None:
        lines.append(f'  |> filter(fn: (r) => r._field == "{validate_field(field)}")')

    if aggregation is not Aggregation.RAW:
        # Booleans cannot be averaged, so they drop out of aggregated queries.
        lines.append(
            f"  |> filter(fn: (r) => not contains(value: r._field, set: {_flux_set()}))"
        )
        lines.append(_aggregate_clause(aggregation, validate_window(window)))

    lines.append('  |> sort(columns: ["_time"])')
    return "\n".join(lines)


def build_latest_query(*, bucket: str, target_id: UUID, lookback: str = "-15m") -> str:
    """Latest value of every field per probe, backing GET /sites/{id}/status."""
    return "\n".join(
        [
            f'from(bucket: "{bucket}")',
            f"  |> range(start: {validate_time(lookback, 'lookback')})",
            f'  |> filter(fn: (r) => r._measurement == "{MEASUREMENT}")',
            f'  |> filter(fn: (r) => r.target_id == "{target_id}")',
            "  |> last()",
        ]
    )


def _flux_set() -> str:
    return "[" + ", ".join(f'"{name}"' for name in sorted(BOOLEAN_FIELDS)) + "]"


def _aggregate_clause(aggregation: Aggregation, window: str) -> str:
    if aggregation in QUANTILES:
        quantile = QUANTILES[aggregation]
        return (
            f"  |> aggregateWindow(every: {window}, createEmpty: false, "
            f"fn: (tables=<-, column) => tables |> quantile(q: {quantile}, "
            'method: "estimate_tdigest"))'
        )
    return (
        f"  |> aggregateWindow(every: {window}, fn: {aggregation}, createEmpty: false)"
    )

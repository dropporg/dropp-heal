from uuid import uuid4

import pytest

from api.models import ProbeType
from api.tsdb.queries import (
    Aggregation,
    InvalidQueryError,
    build_metrics_query,
    validate_time,
    validate_window,
)


def test_relative_and_absolute_times_are_accepted():
    assert validate_time("-2d", "start") == "-2d"
    assert validate_time("2026-08-28T10:00:00Z", "start") == "2026-08-28T10:00:00Z"


@pytest.mark.parametrize(
    "value", ["-2d; drop", 'now()) |> yield(name: "x"', "2 days ago", "", "-2days"]
)
def test_injection_and_garbage_times_are_rejected(value):
    with pytest.raises(InvalidQueryError):
        validate_time(value, "start")


def test_window_must_be_positive():
    assert validate_window("5m") == "5m"
    with pytest.raises(InvalidQueryError):
        validate_window("-5m")


def test_raw_query_has_no_aggregation():
    flux = build_metrics_query(bucket="heal", target_id=uuid4(), start="-2d")
    assert "aggregateWindow" not in flux
    assert "range(start: -2d" in flux


def test_percentile_query_uses_quantile():
    flux = build_metrics_query(
        bucket="heal", target_id=uuid4(), aggregation=Aggregation.P95, window="1h"
    )
    assert "quantile(q: 0.95" in flux
    assert "every: 1h" in flux


def test_aggregated_query_drops_boolean_fields():
    flux = build_metrics_query(
        bucket="heal", target_id=uuid4(), aggregation=Aggregation.MEAN
    )
    assert '"success"' in flux and "not contains" in flux


def test_probe_type_filter_is_applied():
    flux = build_metrics_query(
        bucket="heal", target_id=uuid4(), probe_type=ProbeType.HTTPS
    )
    assert 'r.probe_type == "https"' in flux


def test_unknown_field_is_rejected():
    with pytest.raises(InvalidQueryError):
        build_metrics_query(bucket="heal", target_id=uuid4(), field="latency_ms; drop")

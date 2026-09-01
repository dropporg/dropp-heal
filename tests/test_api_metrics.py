from datetime import UTC, datetime

import pytest

from api.routers.v1 import metrics as metrics_router


class FakeRecord(dict):
    """Stands in for an influxdb_client FluxRecord, which is dict-like."""


class FakeTable:
    def __init__(self, records):
        self.records = records


@pytest.fixture
def influx_records(monkeypatch):
    """Point the metrics endpoints at canned InfluxDB tables."""
    tables: list[FakeTable] = []

    async def query(_flux):
        return tables

    monkeypatch.setattr(metrics_router.influxdb, "query", query)
    monkeypatch.setattr(
        type(metrics_router.influxdb),
        "bucket",
        property(lambda self: "heal"),
        raising=False,
    )
    return tables


async def test_metrics_groups_points_into_series(client, influx_records):
    site_id = (
        await client.post(
            "/api/v1/sites", json={"name": "Arvan", "fqdn": "arvancloud.ir"}
        )
    ).json()["result"]["id"]
    influx_records.append(
        FakeTable(
            [
                FakeRecord(
                    {
                        "probe_type": "https",
                        "_field": "latency_ms",
                        "_value": 86.1,
                        "_time": datetime(2026, 8, 28, 10, tzinfo=UTC),
                    }
                ),
                FakeRecord(
                    {
                        "probe_type": "https",
                        "_field": "latency_ms",
                        "_value": 91.4,
                        "_time": datetime(2026, 8, 28, 11, tzinfo=UTC),
                    }
                ),
            ]
        )
    )

    response = await client.get(f"/api/v1/sites/{site_id}/metrics?start=-2d")
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["start"] == "-2d"
    assert len(result["series"]) == 1
    series = result["series"][0]
    assert series["probe_type"] == "https"
    assert series["field"] == "latency_ms"
    assert [point["value"] for point in series["points"]] == [86.1, 91.4]


async def test_metrics_reports_window_only_when_aggregating(client, influx_records):
    site_id = (
        await client.post(
            "/api/v1/sites", json={"name": "Arvan", "fqdn": "arvancloud.ir"}
        )
    ).json()["result"]["id"]

    raw = (await client.get(f"/api/v1/sites/{site_id}/metrics")).json()["result"]
    assert raw["window"] is None

    aggregated = (
        await client.get(f"/api/v1/sites/{site_id}/metrics?aggregation=p95&window=1h")
    ).json()["result"]
    assert aggregated["window"] == "1h"


async def test_metrics_rejects_an_unparseable_start(client, influx_records):
    site_id = (
        await client.post(
            "/api/v1/sites", json={"name": "Arvan", "fqdn": "arvancloud.ir"}
        )
    ).json()["result"]["id"]
    response = await client.get(f"/api/v1/sites/{site_id}/metrics?start=yesterday")
    assert response.status_code == 422
    assert response.json()["status"]["code"] == 102


async def test_metrics_rejects_an_unknown_aggregation(client, influx_records):
    site_id = (
        await client.post(
            "/api/v1/sites", json={"name": "Arvan", "fqdn": "arvancloud.ir"}
        )
    ).json()["result"]["id"]
    response = await client.get(f"/api/v1/sites/{site_id}/metrics?aggregation=median")
    assert response.status_code == 422


async def test_status_merges_latest_readings_per_probe(client, influx_records):
    site_id = (
        await client.post(
            "/api/v1/sites", json={"name": "Arvan", "fqdn": "arvancloud.ir"}
        )
    ).json()["result"]["id"]
    influx_records.append(
        FakeTable(
            [
                FakeRecord(
                    {
                        "probe_type": "https",
                        "_field": "latency_ms",
                        "_value": 86.1,
                        "_time": datetime(2026, 8, 28, 10, tzinfo=UTC),
                    }
                ),
                FakeRecord(
                    {
                        "probe_type": "https",
                        "_field": "http_status_code",
                        "_value": 200,
                        "_time": datetime(2026, 8, 28, 10, tzinfo=UTC),
                    }
                ),
                FakeRecord(
                    {
                        "probe_type": "https",
                        "_field": "success",
                        "_value": True,
                        "_time": datetime(2026, 8, 28, 10, tzinfo=UTC),
                    }
                ),
            ]
        )
    )

    response = await client.get(f"/api/v1/sites/{site_id}/status")
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "unknown"
    assert result["probes"]["https"] == {
        "success": True,
        "latency_ms": 86.1,
        "status_code": 200,
        "packet_loss_percent": None,
        "checked_at": "2026-08-28T10:00:00Z",
    }


async def test_metrics_for_missing_site_is_not_found(client, influx_records):
    response = await client.get(
        "/api/v1/sites/11111111-1111-1111-1111-111111111111/metrics"
    )
    assert response.status_code == 404

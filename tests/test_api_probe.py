from api.routers import probe as probe_router


async def test_liveness_never_touches_datastores(client, monkeypatch):
    async def fail():
        raise AssertionError("liveness must not check dependencies")

    monkeypatch.setattr(probe_router.database, "ping", fail)
    monkeypatch.setattr(probe_router.influxdb, "ping", fail)
    response = await client.get("/probe/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_reports_ok_when_both_datastores_answer(client, monkeypatch):
    monkeypatch.setattr(probe_router.database, "ping", _returns(True))
    monkeypatch.setattr(probe_router.influxdb, "ping", _returns(True))
    response = await client.get("/probe/ready")
    assert response.status_code == 200
    assert response.json()["result"] == {
        "status": "ready",
        "mysql": "ok",
        "influxdb": "ok",
    }


async def test_readiness_fails_when_a_datastore_is_down(client, monkeypatch):
    monkeypatch.setattr(probe_router.database, "ping", _returns(False))
    monkeypatch.setattr(probe_router.influxdb, "ping", _returns(True))
    response = await client.get("/probe/ready")
    assert response.status_code == 503
    assert response.json()["result"]["mysql"] == "error"


async def test_prometheus_metrics_are_exposed(client):
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "heal_http_requests_total" in response.text
    assert "heal_active_targets" in response.text


def _returns(value):
    async def ping():
        return value

    return ping

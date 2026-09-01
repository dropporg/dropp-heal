"""Each component is its own service; they must not drift into each other."""

from httpx import ASGITransport, AsyncClient

from api.heal import create_app as create_api_app
from api.monitor import create_app as create_worker_app


def paths(app) -> set[str]:
    """Published paths, read from the schema rather than app.routes.

    Included routers stay lazy in app.routes, so the OpenAPI document is the
    reliable view of what a component actually serves.
    """
    return set(app.openapi()["paths"])


def test_api_component_serves_the_rest_api():
    published = paths(create_api_app())
    assert "/api/v1/sites" in published
    assert "/api/v1/sites/{site_id}/metrics" in published
    assert "/probe/live" in published and "/metrics" in published


def test_worker_component_serves_no_rest_api():
    """A worker exposes only what Kubernetes and Prometheus need."""
    published = paths(create_worker_app())
    assert "/probe/live" in published and "/probe/ready" in published
    assert "/metrics" in published
    assert not any(path.startswith("/api/v1") for path in published)


def test_worker_component_hides_the_docs():
    app = create_worker_app()
    assert app.docs_url is None and app.redoc_url is None


async def test_worker_answers_health_but_not_api_requests():
    transport = ASGITransport(app=create_worker_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/probe/live")).status_code == 200
        assert (await client.get("/metrics")).status_code == 200
        assert (await client.get("/api/v1/sites")).status_code == 404


def test_api_component_never_builds_a_scheduler():
    """Only the worker schedules checks; an api replica must never claim leases."""
    app = create_api_app()
    assert getattr(app.state, "scheduler", None) is None

SITE = {"name": "ArvanCloud", "fqdn": "arvancloud.ir"}


async def test_create_returns_created_site(client):
    response = await client.post("/api/v1/sites", json=SITE)
    assert response.status_code == 201
    payload = response.json()
    assert payload["result"]["fqdn"] == "arvancloud.ir"
    assert payload["status"]["code"] == 100


async def test_create_rejects_duplicate_fqdn(client):
    await client.post("/api/v1/sites", json=SITE)
    response = await client.post("/api/v1/sites", json=SITE)
    assert response.status_code == 409
    assert response.json()["status"]["code"] == 105


async def test_create_rejects_invalid_fqdn(client):
    response = await client.post(
        "/api/v1/sites", json={"name": "x", "fqdn": "https://a.ir/p"}
    )
    assert response.status_code == 422
    assert response.json()["status"]["code"] == 102


async def test_list_paginates_and_filters(client):
    await client.post("/api/v1/sites", json=SITE)
    await client.post("/api/v1/sites", json={"name": "Other", "fqdn": "other.example"})

    payload = (await client.get("/api/v1/sites")).json()["result"]
    assert payload["total"] == 2 and payload["page"] == 1

    payload = (await client.get("/api/v1/sites?search=arvan")).json()["result"]
    assert [item["fqdn"] for item in payload["items"]] == ["arvancloud.ir"]


async def test_get_update_and_delete(client):
    site_id = (await client.post("/api/v1/sites", json=SITE)).json()["result"]["id"]

    assert (await client.get(f"/api/v1/sites/{site_id}")).status_code == 200

    response = await client.patch(
        f"/api/v1/sites/{site_id}", json={"description": "cdn"}
    )
    assert response.json()["result"]["description"] == "cdn"

    assert (await client.delete(f"/api/v1/sites/{site_id}")).status_code == 200
    assert (await client.get(f"/api/v1/sites/{site_id}")).status_code == 404


async def test_patch_rejects_unknown_fields(client):
    site_id = (await client.post("/api/v1/sites", json=SITE)).json()["result"]["id"]
    response = await client.patch(
        f"/api/v1/sites/{site_id}", json={"fqdn": "moved.example"}
    )
    assert response.status_code == 422


async def test_enable_and_disable(client):
    site_id = (await client.post("/api/v1/sites", json=SITE)).json()["result"]["id"]

    response = await client.post(f"/api/v1/sites/{site_id}/disable")
    assert response.json()["result"]["is_active"] is False

    response = await client.post(f"/api/v1/sites/{site_id}/enable")
    assert response.json()["result"]["is_active"] is True


async def test_missing_site_returns_not_found_envelope(client):
    response = await client.get("/api/v1/sites/11111111-1111-1111-1111-111111111111")
    assert response.status_code == 404
    body = response.json()
    assert body["status"]["code"] == 104
    assert set(body) == {"result", "status", "_metadata"}

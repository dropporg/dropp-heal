from api.cruds import sites as crud
from api.models import SiteStatus


async def test_create_derives_influxdb_tag(session):
    site = await crud.create(session, {"name": "Arvan", "fqdn": "arvancloud.ir"})
    assert site.influxdb_tag == str(site.id)
    assert site.last_status is SiteStatus.UNKNOWN
    assert site.enabled_probe_types == ["dns", "tcp", "https"]


async def test_get_and_get_by_fqdn(session, site):
    assert (await crud.get(session, site.id)).fqdn == site.fqdn
    assert (await crud.get_by_fqdn(session, site.fqdn)).id == site.id
    assert await crud.get_by_fqdn(session, "missing.example") is None


async def test_list_filters_by_status_and_activity(session):
    healthy = await crud.create(session, {"name": "A", "fqdn": "a.example"})
    await crud.record_check(session, healthy, SiteStatus.HEALTHY)
    await crud.create(session, {"name": "B", "fqdn": "b.example", "is_active": False})

    rows, total = await crud.list_sites(session, status=SiteStatus.HEALTHY)
    assert [row.fqdn for row in rows] == ["a.example"] and total == 1

    rows, _ = await crud.list_sites(session, is_active=False)
    assert [row.fqdn for row in rows] == ["b.example"]


async def test_list_searches_name_and_fqdn(session, site):
    await crud.create(session, {"name": "Other", "fqdn": "other.example"})
    rows, _ = await crud.list_sites(session, search="arvan")
    assert [row.fqdn for row in rows] == ["arvancloud.ir"]
    rows, _ = await crud.list_sites(session, search="Other")
    assert [row.name for row in rows] == ["Other"]


async def test_list_paginates(session):
    for index in range(5):
        await crud.create(session, {"name": f"S{index}", "fqdn": f"s{index}.example"})
    rows, total = await crud.list_sites(session, page=2, page_size=2)
    assert total == 5 and len(rows) == 2


async def test_update_applies_only_given_fields(session, site):
    updated = await crud.update(session, site, {"description": "cdn"})
    assert updated.description == "cdn"
    assert updated.name == "ArvanCloud"


async def test_record_check_stores_status_and_time(session, site):
    updated = await crud.record_check(session, site, SiteStatus.SUSPECTED_FILTERED)
    assert updated.last_status is SiteStatus.SUSPECTED_FILTERED
    assert updated.last_checked_at is not None


async def test_set_active_and_list_active(session, site):
    await crud.set_active(session, site, False)
    assert await crud.list_active(session) == []
    await crud.set_active(session, site, True)
    assert len(await crud.list_active(session)) == 1


async def test_delete_removes_the_site(session, site):
    await crud.delete(session, site)
    assert await crud.get(session, site.id) is None

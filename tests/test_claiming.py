"""Multi-replica scheduling: leases must make checks exactly-once."""

from datetime import timedelta

from api.cruds import sites as crud
from api.models import SiteStatus
from api.models.site import utcnow


async def test_a_new_site_is_immediately_due(session, site):
    claimed = await crud.claim_due(session, worker_id="w1", limit=10, lease_seconds=60)
    assert [row.id for row in claimed] == [site.id]
    assert claimed[0].locked_by == "w1"
    assert claimed[0].locked_until is not None


async def test_a_claimed_site_is_not_handed_to_another_worker(session, site):
    await crud.claim_due(session, worker_id="w1", limit=10, lease_seconds=60)
    assert (
        await crud.claim_due(session, worker_id="w2", limit=10, lease_seconds=60) == []
    )


async def test_an_expired_lease_is_reclaimable(session, site):
    await crud.claim_due(session, worker_id="crashed", limit=10, lease_seconds=60)
    await crud.update(session, site, {"locked_until": utcnow() - timedelta(seconds=1)})

    claimed = await crud.claim_due(session, worker_id="w2", limit=10, lease_seconds=60)
    assert [row.id for row in claimed] == [site.id]
    assert claimed[0].locked_by == "w2"


async def test_completing_a_check_releases_the_lease_and_schedules_the_next(
    session, site
):
    await crud.claim_due(session, worker_id="w1", limit=10, lease_seconds=60)
    completed = await crud.complete_check(
        session,
        site,
        status=SiteStatus.HEALTHY,
        suspicious_streak=0,
        interval_seconds=30,
    )
    assert completed.locked_by is None
    assert completed.locked_until is None
    assert completed.last_status is SiteStatus.HEALTHY
    assert completed.next_check_at > utcnow()

    # Not due again until the interval elapses.
    assert (
        await crud.claim_due(session, worker_id="w2", limit=10, lease_seconds=60) == []
    )


async def test_a_site_becomes_due_again_once_the_interval_passes(session, site):
    await crud.complete_check(
        session,
        site,
        status=SiteStatus.HEALTHY,
        suspicious_streak=0,
        interval_seconds=30,
    )
    await crud.update(session, site, {"next_check_at": utcnow() - timedelta(seconds=1)})
    assert (
        len(await crud.claim_due(session, worker_id="w1", limit=10, lease_seconds=60))
        == 1
    )


async def test_releasing_makes_a_site_immediately_claimable(session, site):
    await crud.claim_due(session, worker_id="w1", limit=10, lease_seconds=60)
    await crud.release(session, site)
    assert (
        len(await crud.claim_due(session, worker_id="w2", limit=10, lease_seconds=60))
        == 1
    )


async def test_inactive_sites_are_never_claimed(session, site):
    await crud.set_active(session, site, False)
    assert (
        await crud.claim_due(session, worker_id="w1", limit=10, lease_seconds=60) == []
    )


async def test_batch_size_bounds_a_claim(session):
    for index in range(5):
        await crud.create(session, {"name": f"S{index}", "fqdn": f"s{index}.example"})
    claimed = await crud.claim_due(session, worker_id="w1", limit=2, lease_seconds=60)
    assert len(claimed) == 2


async def test_the_suspicion_streak_survives_on_the_row(session, site):
    """Filtering evidence must not live in one replica's memory."""
    await crud.complete_check(
        session,
        site,
        status=SiteStatus.TIMEOUT,
        suspicious_streak=1,
        interval_seconds=30,
    )
    reloaded = await crud.get(session, site.id)
    assert reloaded.suspicious_streak == 1

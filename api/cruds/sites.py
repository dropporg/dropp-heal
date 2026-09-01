from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Site, SiteStatus
from api.models.site import utcnow


async def create(session: AsyncSession, data: dict[str, Any]) -> Site:
    """Persist a new site, deriving influxdb_tag when the caller omits it."""
    payload = dict(data)
    payload.setdefault("id", uuid4())
    payload.setdefault("influxdb_tag", str(payload["id"]))
    site = Site(**payload)
    session.add(site)
    await session.commit()
    await session.refresh(site)
    return site


async def get(session: AsyncSession, site_id: UUID) -> Site | None:
    return await session.get(Site, site_id)


async def get_by_fqdn(session: AsyncSession, fqdn: str) -> Site | None:
    result = await session.execute(select(Site).where(Site.fqdn == fqdn))
    return result.scalar_one_or_none()


async def list_sites(
    session: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 50,
    status: SiteStatus | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> tuple[list[Site], int]:
    """Return one page of sites and the total matching the same filters."""
    filters = []
    if status is not None:
        filters.append(Site.last_status == status)
    if is_active is not None:
        filters.append(Site.is_active.is_(is_active))
    if search:
        pattern = f"%{search}%"
        filters.append(or_(Site.name.like(pattern), Site.fqdn.like(pattern)))

    total = (
        await session.scalar(select(func.count()).select_from(Site).where(*filters))
        or 0
    )
    result = await session.execute(
        select(Site)
        .where(*filters)
        .order_by(Site.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def update(session: AsyncSession, site: Site, data: dict[str, Any]) -> Site:
    """Apply a partial update; keys absent from data are left untouched."""
    for field, value in data.items():
        setattr(site, field, value)
    await session.commit()
    await session.refresh(site)
    return site


async def delete(session: AsyncSession, site: Site) -> None:
    await session.delete(site)
    await session.commit()


async def set_active(session: AsyncSession, site: Site, is_active: bool) -> Site:
    return await update(session, site, {"is_active": is_active})


async def record_check(
    session: AsyncSession,
    site: Site,
    status: SiteStatus,
    checked_at: datetime | None = None,
) -> Site:
    """Store the outcome of a probe run. Called by the monitoring engine."""
    return await update(
        session,
        site,
        {"last_status": status, "last_checked_at": checked_at or utcnow()},
    )


async def list_active(session: AsyncSession) -> list[Site]:
    """Every site the monitoring engine should schedule."""
    result = await session.execute(select(Site).where(Site.is_active.is_(True)))
    return list(result.scalars().all())


async def claim_due(
    session: AsyncSession,
    *,
    worker_id: str,
    limit: int,
    lease_seconds: int,
    now: datetime | None = None,
) -> list[Site]:
    """Atomically take ownership of sites that are due for a check.

    Multiple workers run this concurrently. SKIP LOCKED lets each transaction
    take a different batch instead of blocking, so replicas shard the work and
    no site is ever checked twice in the same round. A site whose lease has
    expired -- a crashed worker -- becomes claimable again.
    """
    now = now or utcnow()
    statement = (
        select(Site)
        .where(
            Site.is_active.is_(True),
            or_(Site.next_check_at.is_(None), Site.next_check_at <= now),
            or_(Site.locked_until.is_(None), Site.locked_until <= now),
        )
        .order_by(Site.next_check_at.asc())
        .limit(limit)
    )
    # SQLite, used by the tests, has no row-level locking to skip.
    if session.bind is not None and session.bind.dialect.name in {
        "mysql",
        "postgresql",
    }:
        statement = statement.with_for_update(skip_locked=True)

    sites = list((await session.execute(statement)).scalars().all())
    lease_until = now + timedelta(seconds=lease_seconds)
    for site in sites:
        site.locked_by = worker_id
        site.locked_until = lease_until
    await session.commit()
    return sites


async def complete_check(
    session: AsyncSession,
    site: Site,
    *,
    status: SiteStatus,
    suspicious_streak: int,
    interval_seconds: int,
    checked_at: datetime | None = None,
) -> Site:
    """Store a check's outcome, schedule the next one, and release the lease."""
    checked_at = checked_at or utcnow()
    return await update(
        session,
        site,
        {
            "last_status": status,
            "last_checked_at": checked_at,
            "suspicious_streak": suspicious_streak,
            "next_check_at": checked_at + timedelta(seconds=interval_seconds),
            "locked_by": None,
            "locked_until": None,
        },
    )


async def release(session: AsyncSession, site: Site) -> Site:
    """Drop a lease without recording a result, so another worker may retry."""
    return await update(session, site, {"locked_by": None, "locked_until": None})

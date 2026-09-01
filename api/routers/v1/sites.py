from uuid import UUID

from fastapi import APIRouter, Query, Request

from api.cruds import sites as crud
from api.dependencies import SessionDep
from api.models import SiteStatus
from api.models.site import utcnow
from api.schemas.v1 import SiteCreate, SiteList, SiteRead, SiteUpdate
from api.utils.jsonify import ALREADY_EXISTS, NOT_FOUND, OK, Jsonify

router = APIRouter(prefix="/sites", tags=["sites"])


@router.post("", summary="Create a monitored site")
async def create_site(payload: SiteCreate, session: SessionDep) -> Jsonify:
    if await crud.get_by_fqdn(session, payload.fqdn) is not None:
        return Jsonify(code=ALREADY_EXISTS, metadata=payload.fqdn)
    site = await crud.create(session, payload.model_dump())
    return Jsonify(result=SiteRead.model_validate(site), http_status=201)


@router.get("", summary="List monitored sites")
async def list_sites(
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: SiteStatus | None = Query(None, description="Filter by last known state."),
    is_active: bool | None = Query(None),
    search: str | None = Query(None, description="Match against name or FQDN."),
) -> Jsonify:
    rows, total = await crud.list_sites(
        session,
        page=page,
        page_size=page_size,
        status=status,
        is_active=is_active,
        search=search,
    )
    return Jsonify(
        result=SiteList(
            items=[SiteRead.model_validate(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/{site_id}", summary="Get a site and its latest status")
async def get_site(site_id: UUID, session: SessionDep) -> Jsonify:
    site = await crud.get(session, site_id)
    if site is None:
        return Jsonify(code=NOT_FOUND, metadata=str(site_id))
    return Jsonify(result=SiteRead.model_validate(site))


@router.patch("/{site_id}", summary="Update monitoring configuration")
async def update_site(
    site_id: UUID, payload: SiteUpdate, session: SessionDep
) -> Jsonify:
    site = await crud.get(session, site_id)
    if site is None:
        return Jsonify(code=NOT_FOUND, metadata=str(site_id))
    site = await crud.update(session, site, payload.model_dump(exclude_unset=True))
    return Jsonify(result=SiteRead.model_validate(site))


@router.delete("/{site_id}", summary="Delete a site")
async def delete_site(site_id: UUID, session: SessionDep) -> Jsonify:
    site = await crud.get(session, site_id)
    if site is None:
        return Jsonify(code=NOT_FOUND, metadata=str(site_id))
    await crud.delete(session, site)
    return Jsonify(result={"deleted": str(site_id)})


@router.post("/{site_id}/enable", summary="Enable monitoring")
async def enable_site(site_id: UUID, session: SessionDep) -> Jsonify:
    return await _set_active(site_id, session, True)


@router.post("/{site_id}/disable", summary="Disable monitoring")
async def disable_site(site_id: UUID, session: SessionDep) -> Jsonify:
    return await _set_active(site_id, session, False)


@router.post("/{site_id}/check", summary="Trigger an immediate check")
async def check_site(site_id: UUID, session: SessionDep, request: Request) -> Jsonify:
    """Probe now instead of waiting for the interval, and return the outcome."""
    site = await crud.get(session, site_id)
    if site is None:
        return Jsonify(code=NOT_FOUND, metadata=str(site_id))

    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None:
        return Jsonify(code=OK, result={"status": str(site.last_status), "probes": {}})

    outcome = await scheduler.worker.check(site)
    # An on-demand check records its result but leaves the schedule alone, so
    # it neither delays nor advances the worker's next run.
    await crud.update(
        session,
        site,
        {
            "last_status": outcome.status,
            "last_checked_at": utcnow(),
            "suspicious_streak": outcome.suspicious_streak,
        },
    )
    return Jsonify(
        result={
            "site_id": str(site.id),
            "fqdn": site.fqdn,
            "status": str(outcome.status),
            "probes": {
                str(probe_type): {
                    "success": result.success,
                    "latency_ms": result.latency_ms,
                    "status_code": result.http_status_code,
                    "error": result.error,
                }
                for probe_type, result in outcome.results.items()
            },
        }
    )


async def _set_active(site_id: UUID, session: SessionDep, is_active: bool) -> Jsonify:
    site = await crud.get(session, site_id)
    if site is None:
        return Jsonify(code=NOT_FOUND, metadata=str(site_id))
    site = await crud.set_active(session, site, is_active)
    return Jsonify(result=SiteRead.model_validate(site))

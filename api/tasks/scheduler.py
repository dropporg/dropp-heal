import asyncio
import contextlib
import logging

from api.config import Settings, get_settings
from api.cruds import sites as sites_crud
from api.db import database
from api.models import Site
from api.observability.metrics import ACTIVE_TARGETS, RUNNING_CHECKS
from api.tasks.worker import CheckWorker

logger = logging.getLogger("heal.scheduler")

# How often a worker looks for sites that have come due.
TICK_SECONDS = 1.0


class Scheduler:
    """Distributed monitoring engine.

    Every replica runs the same loop: claim a batch of due sites, check them,
    then write the results and the next due time back. Claiming is a locking
    read, so replicas take disjoint batches and a site is checked exactly once
    per interval no matter how many pods are running. Scheduling state lives in
    MySQL rather than in memory, so restarts and rescheduling do not drift and
    a crashed pod's sites are picked up by another once its lease expires.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._worker = CheckWorker(self._settings)
        self._semaphore = asyncio.Semaphore(self._settings.worker_concurrency)
        self._running: dict[str, asyncio.Task] = {}
        self._loop_task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    @property
    def worker(self) -> CheckWorker:
        return self._worker

    @property
    def worker_id(self) -> str:
        return self._settings.worker_id

    def start(self) -> None:
        if self._loop_task is not None:
            return
        self._stopping.clear()
        self._loop_task = asyncio.create_task(self._run(), name="heal-scheduler")
        logger.info(
            "scheduler started",
            extra={
                "worker_id": self.worker_id,
                "concurrency": self._settings.worker_concurrency,
                "batch_size": self._settings.claim_batch_size,
            },
        )

    async def stop(self, timeout: float = 30.0) -> None:
        """Stop claiming, let in-flight checks finish, then release their leases."""
        self._stopping.set()
        if self._loop_task is not None:
            self._loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._loop_task
            self._loop_task = None
        if self._running:
            logger.info("draining checks", extra={"pending": len(self._running)})
            _, pending = await asyncio.wait(
                list(self._running.values()), timeout=timeout
            )
            for task in pending:
                task.cancel()
        logger.info("scheduler stopped", extra={"worker_id": self.worker_id})

    async def _run(self) -> None:
        while not self._stopping.is_set():
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                # A failure here must never kill the engine.
                logger.exception("scheduler tick failed")
            await asyncio.sleep(TICK_SECONDS)

    async def _tick(self) -> None:
        capacity = self._capacity()
        if capacity <= 0:
            return
        for site in await self._claim(capacity):
            self._running[str(site.id)] = asyncio.create_task(
                self._guarded_check(site), name=f"heal-check-{site.id}"
            )

    def _capacity(self) -> int:
        """Never claim more than this replica can currently run."""
        free = self._settings.worker_concurrency - len(self._running)
        return min(self._settings.claim_batch_size, max(free, 0))

    async def _claim(self, limit: int) -> list[Site]:
        async for session in database.session():
            sites = await sites_crud.claim_due(
                session,
                worker_id=self.worker_id,
                limit=limit,
                lease_seconds=self._settings.lease_seconds,
            )
            ACTIVE_TARGETS.set(len(await sites_crud.list_active(session)))
            return sites
        return []

    def _interval_for(self, site: Site) -> int:
        return site.check_interval or self._settings.check_interval

    async def _guarded_check(self, site: Site) -> None:
        """Run one check under the concurrency limit, isolating its failures."""
        async with self._semaphore:
            RUNNING_CHECKS.inc()
            try:
                outcome = await self._worker.check(site)
                await self._complete(site, outcome)
            except asyncio.CancelledError:
                # Shutting down mid-check: drop the lease so another replica
                # retries immediately instead of waiting for it to expire.
                await self._release(site)
                raise
            except Exception:
                logger.exception("check failed", extra={"target_id": str(site.id)})
                await self._release(site)
            finally:
                RUNNING_CHECKS.dec()
                self._running.pop(str(site.id), None)

    async def _complete(self, site: Site, outcome) -> None:
        try:
            async for session in database.session():
                fresh = await sites_crud.get(session, site.id)
                if fresh is not None:
                    await sites_crud.complete_check(
                        session,
                        fresh,
                        status=outcome.status,
                        suspicious_streak=outcome.suspicious_streak,
                        interval_seconds=self._interval_for(site),
                    )
                break
        except Exception:
            logger.warning(
                "storing check outcome failed",
                extra={"target_id": str(site.id)},
                exc_info=True,
            )

    async def _release(self, site: Site) -> None:
        try:
            async for session in database.session():
                fresh = await sites_crud.get(session, site.id)
                if fresh is not None:
                    await sites_crud.release(session, fresh)
                break
        except Exception:
            logger.warning(
                "releasing lease failed",
                extra={"target_id": str(site.id)},
                exc_info=True,
            )

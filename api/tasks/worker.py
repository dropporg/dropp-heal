import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from api.config import Settings
from api.models import ProbeType, Site, SiteStatus
from api.observability.metrics import (
    CHECK_DURATION,
    CHECKS_FAILED_TOTAL,
    CHECKS_SUCCESS_TOTAL,
    CHECKS_TOTAL,
)
from api.probes import ProbeResult, ProbeTarget, get_probe
from api.tasks.filtering import classify
from api.tsdb import influxdb, to_point
from api.utils.network import is_allowed_target

logger = logging.getLogger("heal.worker")


@dataclass(slots=True)
class CheckOutcome:
    """Result of one check round, for the caller to persist."""

    status: SiteStatus
    results: dict[ProbeType, "ProbeResult"] = field(default_factory=dict)
    suspicious_streak: int = 0


class CheckWorker:
    """Runs one site's probes, stores the metrics, and updates its status."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def target_for(self, site: Site) -> ProbeTarget:
        return ProbeTarget(
            fqdn=site.fqdn,
            timeout=float(site.timeout or self._settings.check_timeout),
            tcp_ports=list(site.tcp_ports or [80, 443]),
            http_method=site.http_method,
            http_path=site.http_path,
            expected_status_codes=list(site.expected_status_codes or [200]),
        )

    def probe_types(self, site: Site) -> list[ProbeType]:
        """Enabled probes, dropping ICMP when it is disabled globally."""
        enabled = [ProbeType(p) for p in (site.enabled_probe_types or [])]
        if not self._settings.icmp_enabled:
            enabled = [p for p in enabled if p is not ProbeType.ICMP]
        return enabled

    async def run_probes(self, site: Site) -> dict[ProbeType, ProbeResult]:
        """Execute every enabled probe concurrently, retrying failures."""
        target = self.target_for(site)
        probe_types = self.probe_types(site)
        results = await asyncio.gather(
            *(self._run_with_retry(probe_type, target) for probe_type in probe_types)
        )
        return dict(zip(probe_types, results, strict=True))

    async def _run_with_retry(
        self, probe_type: ProbeType, target: ProbeTarget
    ) -> ProbeResult:
        probe = get_probe(probe_type)
        label = str(probe_type)
        with CHECK_DURATION.labels(label).time():
            result = await probe.run(target)
            for _ in range(self._settings.check_retries):
                if result.success:
                    break
                result = await probe.run(target)
        CHECKS_TOTAL.labels(label).inc()
        if result.success:
            CHECKS_SUCCESS_TOTAL.labels(label).inc()
        else:
            CHECKS_FAILED_TOTAL.labels(label).inc()
        return result

    async def check(
        self, site: Site
    ) -> tuple[SiteStatus, dict[ProbeType, ProbeResult]]:
        """Probe a site, persist the outcome, and return it.

        Failures are contained here so one bad target never stops the others.
        """
        allowed, _reason = is_allowed_target(
            site.fqdn, allow_private=self._settings.allow_private_targets
        )
        if not allowed:
            logger.warning(
                "target blocked", extra={"target_id": str(site.id), "fqdn": site.fqdn}
            )
            return CheckOutcome(status=SiteStatus.UNKNOWN, suspicious_streak=0)

        started = datetime.now(UTC)
        results = await self.run_probes(site)
        streak = site.suspicious_streak or 0
        status, suspicious = classify(results, streak)
        streak = streak + 1 if suspicious else 0

        logger.info(
            "check complete",
            extra={
                "target_id": str(site.id),
                "fqdn": site.fqdn,
                "status": str(status),
                "duration": (datetime.now(UTC) - started).total_seconds(),
            },
        )
        await self._store_metrics(site, results, status, started)
        return CheckOutcome(status=status, results=results, suspicious_streak=streak)

    async def _store_metrics(
        self,
        site: Site,
        results: dict[ProbeType, ProbeResult],
        status: SiteStatus,
        timestamp: datetime,
    ) -> None:
        if not results:
            return
        points = [
            to_point(
                result,
                target_id=str(site.id),
                fqdn=site.fqdn,
                influxdb_tag=site.influxdb_tag,
                status=str(status),
                timestamp=timestamp,
            )
            for result in results.values()
        ]
        try:
            await influxdb.write(points)
        except Exception:
            logger.warning(
                "influxdb write failed",
                extra={"target_id": str(site.id)},
                exc_info=True,
            )

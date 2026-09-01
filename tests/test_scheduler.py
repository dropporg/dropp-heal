import asyncio

import pytest

from api.config import Settings
from api.models import ProbeType, SiteStatus
from api.probes import ProbeResult
from api.tasks.scheduler import Scheduler
from api.tasks.worker import CheckWorker


@pytest.fixture
def settings() -> Settings:
    return Settings(check_retries=1, worker_concurrency=2, icmp_enabled=False)


def test_icmp_is_dropped_when_disabled(settings, site):
    site.enabled_probe_types = ["dns", "icmp", "https"]
    assert ProbeType.ICMP not in CheckWorker(settings).probe_types(site)


def test_icmp_is_kept_when_enabled(site):
    site.enabled_probe_types = ["dns", "icmp"]
    worker = CheckWorker(Settings(icmp_enabled=True))
    assert ProbeType.ICMP in worker.probe_types(site)


def test_target_uses_site_overrides_before_global_defaults(settings, site):
    site.timeout = 11
    assert CheckWorker(settings).target_for(site).timeout == 11.0
    site.timeout = None
    assert CheckWorker(settings).target_for(site).timeout == float(
        settings.check_timeout
    )


async def test_retries_stop_once_a_probe_succeeds(settings, site, monkeypatch):
    calls = []

    class FlakyProbe:
        async def run(self, target):
            calls.append(1)
            success = len(calls) > 1
            return ProbeResult(probe_type=ProbeType.DNS, success=success)

    monkeypatch.setattr("api.tasks.worker.get_probe", lambda _: FlakyProbe())
    worker = CheckWorker(Settings(check_retries=3))
    result = await worker._run_with_retry(ProbeType.DNS, worker.target_for(site))
    assert result.success is True
    assert len(calls) == 2


async def test_blocked_target_is_not_probed(site, monkeypatch):
    probed = False

    async def run_probes(_):
        nonlocal probed
        probed = True
        return {}

    worker = CheckWorker(Settings(allow_private_targets=False))
    monkeypatch.setattr(worker, "run_probes", run_probes)
    monkeypatch.setattr(
        "api.tasks.worker.is_allowed_target", lambda *a, **k: (False, "private")
    )

    outcome = await worker.check(site)
    assert outcome.status is SiteStatus.UNKNOWN
    assert probed is False and outcome.results == {}


async def test_suspicion_streak_escalates_then_resets(settings, site, monkeypatch):
    outcome = {"success": False}

    async def run_probes(_):
        return {
            ProbeType.DNS: ProbeResult(probe_type=ProbeType.DNS, success=True),
            ProbeType.TCP: ProbeResult(
                probe_type=ProbeType.TCP, success=outcome["success"], timeout=True
            ),
        }

    worker = CheckWorker(settings)
    monkeypatch.setattr(worker, "run_probes", run_probes)
    monkeypatch.setattr(worker, "_store_metrics", _noop)

    # The streak lives on the row, so the caller carries it between rounds the
    # way the scheduler does when a different replica picks the site up.
    first = await worker.check(site)
    assert first.status is SiteStatus.TIMEOUT
    assert first.suspicious_streak == 1

    site.suspicious_streak = first.suspicious_streak
    second = await worker.check(site)
    assert second.status is SiteStatus.SUSPECTED_FILTERED

    outcome["success"] = True
    site.suspicious_streak = second.suspicious_streak
    third = await worker.check(site)
    assert third.status is SiteStatus.HEALTHY
    assert third.suspicious_streak == 0


async def test_scheduler_starts_and_stops_cleanly(settings, monkeypatch):
    scheduler = Scheduler(settings)
    monkeypatch.setattr(scheduler, "_claim", _returns_empty)
    scheduler.start()
    await asyncio.sleep(0.05)
    await scheduler.stop(timeout=1)
    assert scheduler._loop_task is None


async def test_scheduler_survives_a_failing_tick(settings, monkeypatch):
    ticks = []

    async def exploding_tick():
        ticks.append(1)
        raise RuntimeError("database down")

    scheduler = Scheduler(settings)
    monkeypatch.setattr(scheduler, "_tick", exploding_tick)
    monkeypatch.setattr("api.tasks.scheduler.TICK_SECONDS", 0.01)
    scheduler.start()
    await asyncio.sleep(0.05)
    await scheduler.stop(timeout=1)
    assert len(ticks) >= 1


async def _noop(*args, **kwargs):
    return None


async def _returns_empty(*args, **kwargs):
    return []


async def test_checks_are_counted_for_prometheus(settings, site, monkeypatch):
    """The engine's own counters must move, or /metrics reports a dead worker."""
    from api.observability.metrics import (
        CHECKS_FAILED_TOTAL,
        CHECKS_SUCCESS_TOTAL,
        CHECKS_TOTAL,
    )

    def read(counter, label):
        return counter.labels(label)._value.get()

    before = (
        read(CHECKS_TOTAL, "dns"),
        read(CHECKS_SUCCESS_TOTAL, "dns"),
        read(CHECKS_FAILED_TOTAL, "dns"),
    )

    class OkProbe:
        async def run(self, target):
            return ProbeResult(probe_type=ProbeType.DNS, success=True)

    class BadProbe:
        async def run(self, target):
            return ProbeResult(probe_type=ProbeType.DNS, success=False)

    worker = CheckWorker(Settings(check_retries=0))

    monkeypatch.setattr("api.tasks.worker.get_probe", lambda _: OkProbe())
    await worker._run_with_retry(ProbeType.DNS, worker.target_for(site))
    monkeypatch.setattr("api.tasks.worker.get_probe", lambda _: BadProbe())
    await worker._run_with_retry(ProbeType.DNS, worker.target_for(site))

    assert read(CHECKS_TOTAL, "dns") == before[0] + 2
    assert read(CHECKS_SUCCESS_TOTAL, "dns") == before[1] + 1
    assert read(CHECKS_FAILED_TOTAL, "dns") == before[2] + 1

import asyncio

import pytest

from api.models import ProbeType
from api.probes import PROBES, ProbeResult, ProbeTarget, get_probe
from api.probes.dns import DNSProbe
from api.probes.tcp import TCPProbe


def test_registry_covers_every_probe_type():
    assert set(PROBES) == set(ProbeType)


def test_unknown_probe_type_is_rejected():
    with pytest.raises(ValueError):
        get_probe("traceroute")


def test_metric_fields_skip_missing_values():
    result = ProbeResult(probe_type=ProbeType.DNS, success=True, latency_ms=12.5)
    fields = result.metric_fields()
    assert fields["latency_ms"] == 12.5
    assert fields["success"] is True
    assert "ttfb_ms" not in fields


async def test_dns_probe_reports_nxdomain():
    target = ProbeTarget(fqdn="heal-test-nonexistent.invalid", timeout=3)
    result = await DNSProbe().run(target)
    assert result.success is False
    assert result.error == "NXDOMAIN"


async def test_tcp_probe_reports_refused_connection():
    target = ProbeTarget(fqdn="127.0.0.1", timeout=2, tcp_ports=[9])
    result = await TCPProbe().run(target)
    assert result.success is False
    assert "refused" in (result.error or "")


async def test_tcp_probe_reports_timeout(monkeypatch):
    async def never_connects(*args, **kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr("api.probes.tcp.asyncio.open_connection", never_connects)
    result = await TCPProbe().run(
        ProbeTarget(fqdn="example.com", timeout=0.1, tcp_ports=[80])
    )
    assert result.success is False
    assert result.timeout is True


async def test_probes_never_raise_on_failure():
    """A broken target must come back as a result, not an exception."""
    target = ProbeTarget(fqdn="heal-test-nonexistent.invalid", timeout=2)
    for probe_type in (ProbeType.DNS, ProbeType.TCP, ProbeType.HTTP, ProbeType.HTTPS):
        result = await get_probe(probe_type).run(target)
        assert isinstance(result, ProbeResult)
        assert result.success is False

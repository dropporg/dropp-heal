from api.models import ProbeType
from api.probes.base import Probe, ProbeResult, ProbeTarget
from api.probes.dns import DNSProbe
from api.probes.http import HTTPProbe, HTTPSProbe
from api.probes.icmp import ICMPProbe
from api.probes.tcp import TCPProbe

PROBES: dict[ProbeType, type[Probe]] = {
    ProbeType.DNS: DNSProbe,
    ProbeType.ICMP: ICMPProbe,
    ProbeType.TCP: TCPProbe,
    ProbeType.HTTP: HTTPProbe,
    ProbeType.HTTPS: HTTPSProbe,
}


def get_probe(probe_type: ProbeType) -> Probe:
    """Instantiate the probe registered for a type."""
    try:
        return PROBES[ProbeType(probe_type)]()
    except (KeyError, ValueError) as exc:
        raise ValueError(f"Unsupported probe type: {probe_type}") from exc


__all__ = [
    "PROBES",
    "DNSProbe",
    "HTTPProbe",
    "HTTPSProbe",
    "ICMPProbe",
    "Probe",
    "ProbeResult",
    "ProbeTarget",
    "ProbeType",
    "TCPProbe",
    "get_probe",
]

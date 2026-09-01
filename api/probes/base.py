from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from api.models import ProbeType


@dataclass(slots=True)
class ProbeTarget:
    """What a probe needs to know about a site, decoupled from the ORM."""

    fqdn: str
    timeout: float = 5.0
    tcp_ports: list[int] = field(default_factory=lambda: [80, 443])
    http_method: str = "GET"
    http_path: str = "/"
    expected_status_codes: list[int] = field(default_factory=lambda: [200])
    addresses: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProbeResult:
    """One probe execution. Field names match the InfluxDB schema."""

    probe_type: ProbeType
    success: bool
    latency_ms: float | None = None
    dns_latency_ms: float | None = None
    tcp_latency_ms: float | None = None
    tls_latency_ms: float | None = None
    ttfb_ms: float | None = None
    total_latency_ms: float | None = None
    packet_loss_percent: float | None = None
    http_status_code: int | None = None
    timeout: bool = False
    error: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def metric_fields(self) -> dict[str, float | int | bool]:
        """Numeric and boolean fields, ready to write as InfluxDB fields."""
        names = (
            "latency_ms",
            "dns_latency_ms",
            "tcp_latency_ms",
            "tls_latency_ms",
            "ttfb_ms",
            "total_latency_ms",
            "packet_loss_percent",
            "http_status_code",
        )
        fields: dict[str, float | int | bool] = {
            name: getattr(self, name)
            for name in names
            if getattr(self, name) is not None
        }
        fields["success"] = self.success
        fields["timeout"] = self.timeout
        return fields


class Probe(ABC):
    """Base class for every check.

    Subclasses set probe_type and implement run(). New probe kinds (traceroute,
    DoH, QUIC, certificate expiry) only need to subclass this and register.
    """

    probe_type: ClassVar[ProbeType]

    @abstractmethod
    async def run(self, target: ProbeTarget) -> ProbeResult:
        """Execute the check. Must never raise; failures come back as results."""

    def failure(
        self, error: str, *, timeout: bool = False, **kwargs: Any
    ) -> ProbeResult:
        return ProbeResult(
            probe_type=self.probe_type,
            success=False,
            error=error,
            timeout=timeout,
            **kwargs
        )

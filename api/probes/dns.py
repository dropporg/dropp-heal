import asyncio
from time import perf_counter

import dns.asyncresolver
import dns.exception
import dns.resolver

from api.models import ProbeType
from api.probes.base import Probe, ProbeResult, ProbeTarget


class DNSProbe(Probe):
    """Resolve the FQDN and record how long it took."""

    probe_type = ProbeType.DNS

    async def run(self, target: ProbeTarget) -> ProbeResult:
        resolver = dns.asyncresolver.Resolver()
        resolver.lifetime = target.timeout
        resolver.timeout = target.timeout

        started = perf_counter()
        ipv4, ipv6 = [], []
        try:
            answers = await asyncio.gather(
                self._resolve(resolver, target.fqdn, "A"),
                self._resolve(resolver, target.fqdn, "AAAA"),
            )
            ipv4, ipv6 = answers
        except dns.resolver.NXDOMAIN:
            return self.failure("NXDOMAIN")
        except dns.resolver.NoNameservers:
            return self.failure("SERVFAIL")
        except (dns.exception.Timeout, TimeoutError):
            return self.failure("timeout", timeout=True)
        except dns.exception.DNSException as exc:
            return self.failure(f"invalid response: {exc}")

        latency = (perf_counter() - started) * 1000
        if not ipv4 and not ipv6:
            return self.failure("no addresses returned", dns_latency_ms=latency)

        return ProbeResult(
            probe_type=self.probe_type,
            success=True,
            latency_ms=latency,
            dns_latency_ms=latency,
            detail={"ipv4": ipv4, "ipv6": ipv6},
        )

    @staticmethod
    async def _resolve(
        resolver: dns.asyncresolver.Resolver, fqdn: str, rdtype: str
    ) -> list[str]:
        """Return records of one type; an empty answer is not an error."""
        try:
            answer = await resolver.resolve(fqdn, rdtype)
        except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            return []
        return [record.to_text() for record in answer]

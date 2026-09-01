import ssl
from time import perf_counter

import httpx

from api.models import ProbeType
from api.probes.base import Probe, ProbeResult, ProbeTarget


class HTTPProbe(Probe):
    """Request the target over HTTP and record response timings.

    Only headers are awaited for TTFB; the body is streamed and discarded so a
    large page does not turn a connectivity check into a download.
    """

    probe_type = ProbeType.HTTP
    scheme = "http"

    async def run(self, target: ProbeTarget) -> ProbeResult:
        url = f"{self.scheme}://{target.fqdn}{target.http_path or '/'}"
        started = perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=target.timeout, follow_redirects=True
            ) as client:
                request = client.build_request(target.http_method or "GET", url)
                response = await client.send(request, stream=True)
                ttfb = (perf_counter() - started) * 1000
                try:
                    await response.aclose()
                finally:
                    total = (perf_counter() - started) * 1000
        except httpx.TimeoutException:
            return self.failure("timeout", timeout=True)
        except ssl.SSLError as exc:
            return self.failure(f"tls failed: {exc.reason or exc}")
        except httpx.ConnectError as exc:
            message = str(exc).lower()
            if "refused" in message:
                return self.failure("connection refused")
            if "certificate" in message or "ssl" in message:
                return self.failure(f"tls failed: {exc}")
            return self.failure(f"connection failed: {exc}")
        except httpx.HTTPError as exc:
            return self.failure(f"request failed: {exc}")

        expected = target.expected_status_codes or [200]
        success = response.status_code in expected
        return ProbeResult(
            probe_type=self.probe_type,
            success=success,
            latency_ms=total,
            ttfb_ms=ttfb,
            total_latency_ms=total,
            http_status_code=response.status_code,
            error=None if success else f"unexpected status {response.status_code}",
            detail={
                "url": url,
                "redirect_count": len(response.history),
                "expected_status_codes": expected,
            },
        )


class HTTPSProbe(HTTPProbe):
    probe_type = ProbeType.HTTPS
    scheme = "https"

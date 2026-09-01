import asyncio
import ssl
from time import perf_counter

from api.models import ProbeType
from api.probes.base import Probe, ProbeResult, ProbeTarget

TLS_PORTS = {443, 8443}


class TCPProbe(Probe):
    """Open a TCP connection to each configured port.

    On TLS ports the handshake is timed separately, which is what distinguishes
    a reachable host from one whose TLS is being interfered with.
    """

    probe_type = ProbeType.TCP

    async def run(self, target: ProbeTarget) -> ProbeResult:
        ports = target.tcp_ports or [80]
        results = await asyncio.gather(
            *(self._connect(target, port) for port in ports), return_exceptions=False
        )
        succeeded = [r for r in results if r["success"]]
        if not succeeded:
            first = results[0]
            return self.failure(
                first["error"] or "connection failed",
                timeout=first["timeout"],
                detail={"ports": results},
            )

        fastest = min(succeeded, key=lambda r: r["tcp_latency_ms"])
        tls_latencies = [r["tls_latency_ms"] for r in succeeded if r["tls_latency_ms"]]
        return ProbeResult(
            probe_type=self.probe_type,
            success=True,
            latency_ms=fastest["tcp_latency_ms"],
            tcp_latency_ms=fastest["tcp_latency_ms"],
            tls_latency_ms=min(tls_latencies) if tls_latencies else None,
            detail={"ports": results},
        )

    async def _connect(self, target: ProbeTarget, port: int) -> dict:
        outcome = {
            "port": port,
            "success": False,
            "tcp_latency_ms": None,
            "tls_latency_ms": None,
            "timeout": False,
            "error": None,
        }
        started = perf_counter()
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(target.fqdn, port), timeout=target.timeout
            )
            outcome["tcp_latency_ms"] = (perf_counter() - started) * 1000
            try:
                if port in TLS_PORTS:
                    outcome["tls_latency_ms"] = await self._handshake(target, writer)
                outcome["success"] = True
            finally:
                writer.close()
                await asyncio.wait_for(writer.wait_closed(), timeout=target.timeout)
        except TimeoutError:
            outcome["timeout"] = True
            outcome["error"] = "timeout"
        except ConnectionRefusedError:
            outcome["error"] = "connection refused"
        except ssl.SSLError as exc:
            outcome["error"] = f"tls failed: {exc.reason or exc}"
        except OSError as exc:
            outcome["error"] = str(exc)
        return outcome

    @staticmethod
    async def _handshake(target: ProbeTarget, writer: asyncio.StreamWriter) -> float:
        """Upgrade an open socket to TLS and time only the handshake."""
        context = ssl.create_default_context()
        started = perf_counter()
        await asyncio.wait_for(
            writer.start_tls(context, server_hostname=target.fqdn),
            timeout=target.timeout,
        )
        return (perf_counter() - started) * 1000

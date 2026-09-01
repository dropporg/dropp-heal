import asyncio
import os
import socket
import struct
from time import perf_counter

from api.models import ProbeType
from api.probes.base import Probe, ProbeResult, ProbeTarget

ECHO_REQUEST = 8
ECHO_REPLY = 0
PACKETS = 4


class ICMPUnavailableError(RuntimeError):
    """Raised when the kernel denies both unprivileged and raw ICMP sockets."""


class ICMPProbe(Probe):
    """Ping the target and record round-trip latency and packet loss.

    Tries the unprivileged datagram socket first (Linux ping_group_range) and
    falls back to a raw socket. Both are commonly denied inside containers, so
    this probe is optional and reports unavailability instead of failing loudly.
    """

    probe_type = ProbeType.ICMP

    async def run(self, target: ProbeTarget) -> ProbeResult:
        try:
            address = await asyncio.get_running_loop().getaddrinfo(
                target.fqdn, None, family=socket.AF_INET, type=socket.SOCK_DGRAM
            )
            host = address[0][4][0]
        except socket.gaierror as exc:
            return self.failure(f"dns failed: {exc}")

        latencies: list[float] = []
        lost = 0
        error: str | None = None
        for sequence in range(PACKETS):
            try:
                latencies.append(await self._ping(host, sequence, target.timeout))
            except ICMPUnavailableError as exc:
                return self.failure(f"icmp unavailable: {exc}")
            except TimeoutError:
                lost += 1
                error = "timeout"
            except OSError as exc:
                lost += 1
                error = str(exc)

        loss = lost / PACKETS * 100
        if not latencies:
            return self.failure(
                error or "no reply",
                timeout=error == "timeout",
                packet_loss_percent=loss,
            )
        return ProbeResult(
            probe_type=self.probe_type,
            success=True,
            latency_ms=sum(latencies) / len(latencies),
            packet_loss_percent=loss,
            detail={
                "address": host,
                "min_ms": min(latencies),
                "max_ms": max(latencies),
                "packets_sent": PACKETS,
            },
        )

    async def _ping(self, host: str, sequence: int, timeout: float) -> float:
        loop = asyncio.get_running_loop()
        sock = self._socket()
        try:
            sock.setblocking(False)
            identifier = os.getpid() & 0xFFFF
            packet = self._packet(identifier, sequence)
            started = perf_counter()
            await loop.sock_sendto(sock, packet, (host, 0))
            while True:
                data = await asyncio.wait_for(
                    loop.sock_recv(sock, 1024), timeout=timeout
                )
                if self._is_reply(data, sequence):
                    return (perf_counter() - started) * 1000
        finally:
            sock.close()

    @staticmethod
    def _socket() -> socket.socket:
        try:
            return socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_ICMP)
        except PermissionError:
            pass
        try:
            return socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        except PermissionError as exc:
            raise ICMPUnavailableError("raw socket permission denied") from exc

    @staticmethod
    def _packet(identifier: int, sequence: int) -> bytes:
        header = struct.pack("!BBHHH", ECHO_REQUEST, 0, 0, identifier, sequence)
        payload = b"heal-probe"
        checksum = ICMPProbe._checksum(header + payload)
        header = struct.pack("!BBHHH", ECHO_REQUEST, 0, checksum, identifier, sequence)
        return header + payload

    @staticmethod
    def _is_reply(data: bytes, sequence: int) -> bool:
        # A raw socket hands back the IP header; a datagram socket does not.
        offset = (data[0] & 0x0F) * 4 if data and data[0] >> 4 == 4 else 0
        if len(data) < offset + 8:
            return False
        icmp_type, _, _, _, reply_sequence = struct.unpack(
            "!BBHHH", data[offset : offset + 8]
        )
        return icmp_type == ECHO_REPLY and reply_sequence == sequence

    @staticmethod
    def _checksum(data: bytes) -> int:
        if len(data) % 2:
            data += b"\x00"
        total = 0
        for index in range(0, len(data), 2):
            total += (data[index] << 8) + data[index + 1]
            total = (total & 0xFFFF) + (total >> 16)
        return ~total & 0xFFFF

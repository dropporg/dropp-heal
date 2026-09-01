from api.models import ProbeType, SiteStatus
from api.probes import ProbeResult

# A target must look suspicious this many rounds in a row before Heal will
# report suspected_filtered. One failed request is never enough.
FILTERING_STREAK_THRESHOLD = 2

# ICMP is frequently dropped by networks that carry traffic fine, so it never
# contributes to a filtering verdict.
REACHABILITY_PROBES = (ProbeType.DNS, ProbeType.TCP, ProbeType.HTTP, ProbeType.HTTPS)


def classify(
    results: dict[ProbeType, ProbeResult], suspicious_streak: int = 0
) -> tuple[SiteStatus, bool]:
    """Infer a site's state from one round of probe results.

    Returns the state and whether this round looked like filtering, which the
    caller accumulates into suspicious_streak. The verdict is a heuristic and
    never a certain claim that filtering is happening.
    """
    considered = {p: r for p, r in results.items() if p in REACHABILITY_PROBES}
    if not considered:
        return SiteStatus.UNKNOWN, False

    dns = considered.get(ProbeType.DNS)
    tcp = considered.get(ProbeType.TCP)
    web = considered.get(ProbeType.HTTPS) or considered.get(ProbeType.HTTP)

    if dns is not None and not dns.success:
        # Bad answers, rather than no answer, hint at DNS-level interference.
        if dns.error and "no addresses" in dns.error:
            return _filtered_or(SiteStatus.DNS_FAILED, suspicious_streak), True
        return (SiteStatus.TIMEOUT if dns.timeout else SiteStatus.DNS_FAILED), False

    dns_ok = dns is None or dns.success

    if tcp is not None and not tcp.success:
        if tcp.timeout and dns_ok:
            # Resolvable but silently dropped is the classic filtering signal.
            return _filtered_or(SiteStatus.TIMEOUT, suspicious_streak), True
        if tcp.error and "refused" in tcp.error:
            return SiteStatus.CONNECTION_REFUSED, False
        return SiteStatus.UNREACHABLE, False

    if web is not None and not web.success:
        tcp_ok = tcp is None or tcp.success
        if web.error and "tls failed" in web.error:
            # Connection accepted but TLS fails: possible SNI-based blocking.
            status = (
                _filtered_or(SiteStatus.TLS_FAILED, suspicious_streak)
                if tcp_ok
                else SiteStatus.TLS_FAILED
            )
            return status, tcp_ok
        if web.timeout:
            status = (
                _filtered_or(SiteStatus.TIMEOUT, suspicious_streak)
                if tcp_ok
                else SiteStatus.TIMEOUT
            )
            return status, tcp_ok
        if web.http_status_code is not None:
            return SiteStatus.HTTP_ERROR, False
        return SiteStatus.UNREACHABLE, False

    if all(result.success for result in considered.values()):
        # ICMP loss alone never downgrades a site that answers over HTTP.
        return SiteStatus.HEALTHY, False

    return SiteStatus.DEGRADED, False


def _filtered_or(status: SiteStatus, suspicious_streak: int) -> SiteStatus:
    """Escalate to suspected_filtered only once the streak passes the threshold."""
    if suspicious_streak + 1 >= FILTERING_STREAK_THRESHOLD:
        return SiteStatus.SUSPECTED_FILTERED
    return status

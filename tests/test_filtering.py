from api.models import ProbeType, SiteStatus
from api.probes import ProbeResult
from api.tasks.filtering import FILTERING_STREAK_THRESHOLD, classify


def ok(probe_type: ProbeType) -> ProbeResult:
    return ProbeResult(probe_type=probe_type, success=True, latency_ms=10.0)


def fail(
    probe_type: ProbeType, error: str | None = None, timeout: bool = False
) -> ProbeResult:
    return ProbeResult(
        probe_type=probe_type, success=False, error=error, timeout=timeout
    )


def test_all_probes_succeeding_is_healthy():
    results = {ProbeType.DNS: ok(ProbeType.DNS), ProbeType.HTTPS: ok(ProbeType.HTTPS)}
    assert classify(results)[0] is SiteStatus.HEALTHY


def test_icmp_failure_alone_does_not_mark_site_unhealthy():
    results = {
        ProbeType.DNS: ok(ProbeType.DNS),
        ProbeType.HTTPS: ok(ProbeType.HTTPS),
        ProbeType.ICMP: fail(ProbeType.ICMP, "timeout", timeout=True),
    }
    assert classify(results)[0] is SiteStatus.HEALTHY


def test_dns_failure_reports_dns_failed():
    assert (
        classify({ProbeType.DNS: fail(ProbeType.DNS, "NXDOMAIN")})[0]
        is SiteStatus.DNS_FAILED
    )


def test_connection_refused_is_not_filtering():
    results = {
        ProbeType.DNS: ok(ProbeType.DNS),
        ProbeType.TCP: fail(ProbeType.TCP, "connection refused"),
    }
    status, suspicious = classify(results)
    assert status is SiteStatus.CONNECTION_REFUSED
    assert suspicious is False


def test_single_timeout_is_not_yet_filtering():
    results = {
        ProbeType.DNS: ok(ProbeType.DNS),
        ProbeType.TCP: fail(ProbeType.TCP, "timeout", timeout=True),
    }
    status, suspicious = classify(results, suspicious_streak=0)
    assert status is SiteStatus.TIMEOUT
    assert suspicious is True


def test_repeated_timeouts_with_working_dns_suspect_filtering():
    results = {
        ProbeType.DNS: ok(ProbeType.DNS),
        ProbeType.TCP: fail(ProbeType.TCP, "timeout", timeout=True),
    }
    status, _ = classify(results, suspicious_streak=FILTERING_STREAK_THRESHOLD - 1)
    assert status is SiteStatus.SUSPECTED_FILTERED


def test_tls_failure_over_working_tcp_suspects_filtering():
    results = {
        ProbeType.DNS: ok(ProbeType.DNS),
        ProbeType.TCP: ok(ProbeType.TCP),
        ProbeType.HTTPS: fail(ProbeType.HTTPS, "tls failed: handshake"),
    }
    status, _ = classify(results, suspicious_streak=FILTERING_STREAK_THRESHOLD - 1)
    assert status is SiteStatus.SUSPECTED_FILTERED


def test_unexpected_status_code_is_http_error():
    web = ProbeResult(probe_type=ProbeType.HTTPS, success=False, http_status_code=503)
    results = {ProbeType.DNS: ok(ProbeType.DNS), ProbeType.HTTPS: web}
    assert classify(results)[0] is SiteStatus.HTTP_ERROR


def test_no_results_is_unknown():
    assert classify({})[0] is SiteStatus.UNKNOWN

from enum import StrEnum


class ProbeType(StrEnum):
    DNS = "dns"
    ICMP = "icmp"
    TCP = "tcp"
    HTTP = "http"
    HTTPS = "https"


class SiteStatus(StrEnum):
    """Calculated health state of a target.

    SUSPECTED_FILTERED is heuristic and never a certain claim of filtering.
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"
    DNS_FAILED = "dns_failed"
    TIMEOUT = "timeout"
    CONNECTION_REFUSED = "connection_refused"
    TLS_FAILED = "tls_failed"
    HTTP_ERROR = "http_error"
    SUSPECTED_FILTERED = "suspected_filtered"
    UNKNOWN = "unknown"

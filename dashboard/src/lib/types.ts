/** Mirrors api/schemas/v1 and api/models/enums.py. */

export const PROBE_TYPES = ["dns", "icmp", "tcp", "http", "https"] as const;
export type ProbeType = (typeof PROBE_TYPES)[number];

export const SITE_STATUSES = [
  "healthy",
  "degraded",
  "unreachable",
  "dns_failed",
  "timeout",
  "connection_refused",
  "tls_failed",
  "http_error",
  "suspected_filtered",
  "unknown",
] as const;
export type SiteStatus = (typeof SITE_STATUSES)[number];

/** Application codes from api/utils/jsonify.py, independent of HTTP status. */
export const CODE = {
  OK: 100,
  NOT_IMPLEMENTED: 101,
  INVALID_SCHEMA: 102,
  DATABASE_ERROR: 103,
  NOT_FOUND: 104,
  ALREADY_EXISTS: 105,
  UNSUPPORTED_PROBE: 106,
  MONITORING_ERROR: 107,
  FORBIDDEN_TARGET: 108,
  INTERNAL_ERROR: 109,
} as const;

export interface Envelope<T> {
  result: T;
  status: { code: number; message: string };
  _metadata: string;
}

export interface Site {
  id: string;
  name: string;
  fqdn: string;
  description: string | null;
  is_active: boolean;
  check_interval: number | null;
  timeout: number | null;
  enabled_probe_types: ProbeType[];
  http_method: string;
  http_path: string;
  expected_status_codes: number[];
  tcp_ports: number[];
  influxdb_tag: string;
  last_status: SiteStatus;
  last_checked_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SiteList {
  items: Site[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProbeSnapshot {
  success: boolean | null;
  latency_ms: number | null;
  status_code: number | null;
  packet_loss_percent: number | null;
  checked_at: string | null;
}

export interface SiteStatusRead {
  site_id: string;
  fqdn: string;
  status: SiteStatus;
  last_checked_at: string | null;
  probes: Partial<Record<ProbeType, ProbeSnapshot>>;
}

export interface MetricPoint {
  time: string;
  value: number | null;
}

export interface MetricSeries {
  probe_type: ProbeType;
  field: string;
  points: MetricPoint[];
}

export type Aggregation = "raw" | "mean" | "min" | "max" | "p50" | "p95" | "p99";

export interface MetricsRead {
  site_id: string;
  fqdn: string;
  start: string;
  end: string;
  aggregation: Aggregation;
  window: string | null;
  series: MetricSeries[];
}

export interface CheckResult {
  site_id: string;
  fqdn: string;
  status: SiteStatus;
  probes: Record<
    string,
    {
      success: boolean;
      latency_ms: number | null;
      status_code: number | null;
      error: string | null;
    }
  >;
}

import type { SiteStatus } from "./types";

/**
 * Colour encodes how certain the verdict is, not just how bad it is.
 * Hard failures are red; `suspected_filtered` is violet because Heal never
 * claims filtering with certainty, and reading it as an outage would be wrong.
 */
export type Certainty = "good" | "warning" | "failed" | "suspected" | "unknown";

interface StatusMeta {
  label: string;
  certainty: Certainty;
  /** Shown under the headline verdict on the overview. */
  detail: string;
}

export const STATUS_META: Record<SiteStatus, StatusMeta> = {
  healthy: {
    label: "Healthy",
    certainty: "good",
    detail: "Answering normally across every enabled probe.",
  },
  degraded: {
    label: "Degraded",
    certainty: "warning",
    detail: "Reachable, but some probes are failing.",
  },
  unreachable: {
    label: "Unreachable",
    certainty: "failed",
    detail: "No probe could reach the target.",
  },
  dns_failed: {
    label: "DNS failed",
    certainty: "failed",
    detail: "The hostname did not resolve.",
  },
  timeout: {
    label: "Timed out",
    certainty: "failed",
    detail: "Connections opened but never answered.",
  },
  connection_refused: {
    label: "Refused",
    certainty: "failed",
    detail: "The host actively refused the connection.",
  },
  tls_failed: {
    label: "TLS failed",
    certainty: "failed",
    detail: "The TLS handshake did not complete.",
  },
  http_error: {
    label: "HTTP error",
    certainty: "warning",
    detail: "Answered with an unexpected status code.",
  },
  suspected_filtered: {
    label: "Suspected filtered",
    certainty: "suspected",
    detail: "Repeated evidence consistent with filtering. Not a certainty.",
  },
  unknown: {
    label: "Not yet checked",
    certainty: "unknown",
    detail: "Waiting for the first probe round.",
  },
};

export const CERTAINTY_COLOR: Record<Certainty, string> = {
  good: "var(--signal-good)",
  warning: "var(--signal-warn)",
  failed: "var(--signal-fail)",
  suspected: "var(--signal-suspect)",
  unknown: "var(--signal-idle)",
};

export function certaintyOf(status: SiteStatus): Certainty {
  return STATUS_META[status]?.certainty ?? "unknown";
}

export function colorOf(status: SiteStatus): string {
  return CERTAINTY_COLOR[certaintyOf(status)];
}

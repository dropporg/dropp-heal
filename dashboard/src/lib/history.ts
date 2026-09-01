import type { MetricSeries, SiteStatus } from "./types";

/**
 * Rebuild each check round's verdict from raw probe metrics.
 *
 * The API stores the calculated status as a tag on every point, but only the
 * latest verdict is kept in MySQL. Recovering the per-round history from the
 * time series is what lets the evidence strip show how a suspicion built up.
 */
export function roundsFromSeries(series: MetricSeries[], limit = 60): SiteStatus[] {
  const byTime = new Map<string, { success: number; failed: number }>();

  for (const line of series) {
    if (line.field !== "success") continue;
    for (const point of line.points) {
      const bucket = byTime.get(point.time) ?? { success: 0, failed: 0 };
      if (point.value) bucket.success += 1;
      else bucket.failed += 1;
      byTime.set(point.time, bucket);
    }
  }

  return [...byTime.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-limit)
    .map(([, counts]) => {
      if (counts.failed === 0) return "healthy" as SiteStatus;
      if (counts.success === 0) return "unreachable" as SiteStatus;
      return "degraded" as SiteStatus;
    });
}

/** Latency of one probe over time, for the overview sparkline. */
export function latencyPoints(series: MetricSeries[], field = "latency_ms") {
  const line =
    series.find((s) => s.field === field && s.probe_type === "https") ??
    series.find((s) => s.field === field);
  return line?.points.filter((p) => p.value !== null) ?? [];
}

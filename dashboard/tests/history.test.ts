import { describe, expect, it } from "vitest";

import { latencyPoints, roundsFromSeries } from "@/lib/history";
import type { MetricSeries } from "@/lib/types";

function successSeries(probe: MetricSeries["probe_type"], values: [string, boolean][]): MetricSeries {
  return {
    probe_type: probe,
    field: "success",
    points: values.map(([time, value]) => ({ time, value: value ? 1 : 0 })),
  };
}

describe("roundsFromSeries", () => {
  it("marks a round healthy when every probe succeeded", () => {
    const series = [
      successSeries("dns", [["t1", true]]),
      successSeries("https", [["t1", true]]),
    ];
    expect(roundsFromSeries(series)).toEqual(["healthy"]);
  });

  it("marks a round unreachable when every probe failed", () => {
    const series = [
      successSeries("dns", [["t1", false]]),
      successSeries("https", [["t1", false]]),
    ];
    expect(roundsFromSeries(series)).toEqual(["unreachable"]);
  });

  it("marks a round degraded when probes disagree", () => {
    // DNS resolving while HTTPS fails is the mixed signal filtering produces.
    const series = [
      successSeries("dns", [["t1", true]]),
      successSeries("https", [["t1", false]]),
    ];
    expect(roundsFromSeries(series)).toEqual(["degraded"]);
  });

  it("orders rounds oldest first so the strip reads left to right", () => {
    const series = [
      successSeries("dns", [
        ["2026-08-30T12:00:00Z", true],
        ["2026-08-30T10:00:00Z", false],
        ["2026-08-30T11:00:00Z", true],
      ]),
    ];
    expect(roundsFromSeries(series)).toEqual(["unreachable", "healthy", "healthy"]);
  });

  it("keeps only the most recent rounds when asked for a limit", () => {
    const series = [
      successSeries(
        "dns",
        Array.from({ length: 10 }, (_, index) => [`t${index}`, index > 7] as [string, boolean]),
      ),
    ];
    const rounds = roundsFromSeries(series, 3);
    expect(rounds).toHaveLength(3);
    expect(rounds.at(-1)).toBe("healthy");
  });

  it("ignores fields other than success", () => {
    const series: MetricSeries[] = [
      { probe_type: "dns", field: "latency_ms", points: [{ time: "t1", value: 12 }] },
    ];
    expect(roundsFromSeries(series)).toEqual([]);
  });
});

describe("latencyPoints", () => {
  it("prefers the https trace, which is what users actually experience", () => {
    const series: MetricSeries[] = [
      { probe_type: "dns", field: "latency_ms", points: [{ time: "t1", value: 5 }] },
      { probe_type: "https", field: "latency_ms", points: [{ time: "t1", value: 90 }] },
    ];
    expect(latencyPoints(series).map((point) => point.value)).toEqual([90]);
  });

  it("falls back to any probe when https is not enabled", () => {
    const series: MetricSeries[] = [
      { probe_type: "tcp", field: "latency_ms", points: [{ time: "t1", value: 30 }] },
    ];
    expect(latencyPoints(series).map((point) => point.value)).toEqual([30]);
  });

  it("drops gaps so a broken round does not plot as zero", () => {
    const series: MetricSeries[] = [
      {
        probe_type: "https",
        field: "latency_ms",
        points: [
          { time: "t1", value: 90 },
          { time: "t2", value: null },
        ],
      },
    ];
    expect(latencyPoints(series)).toHaveLength(1);
  });
});

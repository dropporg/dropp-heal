"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { axisTime, latency } from "@/lib/format";
import type { MetricSeries, ProbeType } from "@/lib/types";

/** Each probe keeps its own hue so a line means the same thing on every chart. */
const PROBE_COLOR: Record<ProbeType, string> = {
  dns: "#7f8fa8",
  icmp: "#0e8a78",
  tcp: "#2f6fd0",
  http: "#bd7708",
  https: "#6f42d4",
};

interface Row {
  time: string;
  [probe: string]: string | number | null;
}

export function LatencyChart({
  series,
  field,
  spanHours,
}: {
  series: MetricSeries[];
  field: string;
  spanHours: number;
}) {
  const lines = series.filter((line) => line.field === field);

  const rows = new Map<string, Row>();
  for (const line of lines) {
    for (const point of line.points) {
      const row = rows.get(point.time) ?? { time: point.time };
      row[line.probe_type] = point.value;
      rows.set(point.time, row);
    }
  }
  const data = [...rows.values()].sort((a, b) => a.time.localeCompare(b.time));

  if (data.length === 0) {
    return (
      <div className="flex h-[300px] flex-col items-center justify-center gap-1">
        <p className="font-display text-base font-semibold">Nothing recorded in this window</p>
        <p className="text-sm text-muted">
          Try a longer range, or wait for the next round to complete.
        </p>
      </div>
    );
  }

  return (
    <div className="h-[300px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid stroke="var(--rule)" vertical={false} />
          <XAxis
            dataKey="time"
            tickFormatter={(value: string) => axisTime(value, spanHours)}
            stroke="var(--ink-faint)"
            tick={{ fontSize: 11, fontFamily: "var(--font-mono)" }}
            tickLine={false}
            minTickGap={44}
          />
          <YAxis
            stroke="var(--ink-faint)"
            tick={{ fontSize: 11, fontFamily: "var(--font-mono)" }}
            tickLine={false}
            axisLine={false}
            width={56}
            tickFormatter={(value: number) => `${Math.round(value)}`}
          />
          <Tooltip
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--rule)",
              borderRadius: 2,
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              color: "var(--ink)",
            }}
            labelFormatter={(value) => new Date(String(value)).toLocaleString()}
            formatter={(value, name) => [latency(Number(value)), String(name)]}
          />
          {lines.map((line) => (
            <Line
              key={line.probe_type}
              type="monotone"
              dataKey={line.probe_type}
              name={line.probe_type}
              stroke={PROBE_COLOR[line.probe_type]}
              strokeWidth={1.75}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>

      <ul className="mt-3 flex flex-wrap gap-4">
        {lines.map((line) => (
          <li key={line.probe_type} className="flex items-center gap-1.5">
            <span
              className="h-0.5 w-4"
              style={{ background: PROBE_COLOR[line.probe_type] }}
              aria-hidden
            />
            <span className="eyebrow">{line.probe_type}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

"use client";

import type { MetricPoint } from "@/lib/types";

/** Bare latency trace: no axes, no grid, just the shape of the last window. */
export function Sparkline({
  points,
  width = 132,
  height = 26,
  color = "var(--signal-good)",
}: {
  points: MetricPoint[];
  width?: number;
  height?: number;
  color?: string;
}) {
  const values = points.map((p) => p.value ?? 0);
  if (values.length < 2) {
    return <span className="text-xs text-faint">not enough data</span>;
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = width / (values.length - 1);
  const path = values
    .map((value, index) => {
      const x = index * step;
      const y = height - ((value - min) / span) * (height - 4) - 2;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg width={width} height={height} className="overflow-visible" aria-hidden>
      <path d={path} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" />
      <circle cx={width} cy={height - ((values[values.length - 1] - min) / span) * (height - 4) - 2} r={2} fill={color} />
    </svg>
  );
}

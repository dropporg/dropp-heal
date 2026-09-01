"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { api } from "@/lib/api";
import { latency, relativeTime } from "@/lib/format";
import { latencyPoints, roundsFromSeries } from "@/lib/history";
import { colorOf } from "@/lib/status";
import type { Site } from "@/lib/types";

import { EvidenceStrip } from "./EvidenceStrip";
import { Sparkline } from "./Sparkline";
import { StatusLabel } from "./StatusMark";

export function TargetRow({ site }: { site: Site }) {
  const { data } = useQuery({
    queryKey: ["metrics", site.id, "row"],
    queryFn: () => api.getMetrics(site.id, { start: "-6h" }),
  });

  const series = data?.series ?? [];
  const rounds = roundsFromSeries(series, 48);
  const points = latencyPoints(series);
  const newest = points.at(-1)?.value ?? null;
  const color = colorOf(site.last_status);

  return (
    <Link
      href={`/sites/${site.id}`}
      className="grid grid-cols-[1fr_auto] items-center gap-4 border-b border-rule px-4 py-3.5 transition-colors last:border-b-0 hover:bg-sunk md:grid-cols-[minmax(0,2fr)_11rem_9rem_1fr_5rem]"
    >
      <div className="min-w-0">
        <p className="truncate font-display text-base font-semibold">{site.name}</p>
        <p className="tabular truncate text-xs text-muted">{site.fqdn}</p>
        <div className="mt-1.5 flex items-center gap-2 md:hidden">
          <StatusLabel status={site.last_status} />
          <span className="text-xs text-faint">{relativeTime(site.last_checked_at)}</span>
        </div>
      </div>

      <div className="hidden md:block">
        <StatusLabel status={site.last_status} />
        <p className="mt-0.5 text-xs text-faint">{relativeTime(site.last_checked_at)}</p>
      </div>

      <div className="hidden min-w-0 md:block">
        <p className="eyebrow mb-1">Last 6h</p>
        <EvidenceStrip rounds={rounds} fill label={`${site.name} check history`} />
      </div>

      <div className="hidden items-center gap-3 md:flex">
        <Sparkline points={points} color={color} />
      </div>

      <div className="text-right">
        <p className="tabular text-base font-semibold">{latency(newest)}</p>
        <p className="eyebrow">latency</p>
      </div>
    </Link>
  );
}

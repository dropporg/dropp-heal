"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { use, useState } from "react";

import { EvidenceStrip } from "@/components/EvidenceStrip";
import { LatencyChart } from "@/components/LatencyChart";
import { Panel } from "@/components/Panel";
import { ProbeCards } from "@/components/ProbeCards";
import { StatusLabel } from "@/components/StatusMark";
import { api, type ApiError } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { roundsFromSeries } from "@/lib/history";
import { STATUS_META } from "@/lib/status";
import type { Aggregation } from "@/lib/types";

const RANGES = [
  { label: "1h", start: "-1h", hours: 1, window: "1m" },
  { label: "6h", start: "-6h", hours: 6, window: "5m" },
  { label: "24h", start: "-24h", hours: 24, window: "15m" },
  { label: "2d", start: "-2d", hours: 48, window: "30m" },
  { label: "7d", start: "-7d", hours: 168, window: "2h" },
] as const;

const AGGREGATIONS: Aggregation[] = ["raw", "mean", "p50", "p95", "p99", "max"];

export default function SitePage({ params }: { params: Promise<{ siteId: string }> }) {
  const { siteId } = use(params);
  const queryClient = useQueryClient();
  const [range, setRange] = useState<(typeof RANGES)[number]>(RANGES[1]);
  const [aggregation, setAggregation] = useState<Aggregation>("raw");

  const site = useQuery({ queryKey: ["site", siteId], queryFn: () => api.getSite(siteId) });
  const status = useQuery({
    queryKey: ["status", siteId],
    queryFn: () => api.getStatus(siteId),
  });
  const metrics = useQuery({
    queryKey: ["metrics", siteId, range.start, aggregation],
    queryFn: () =>
      api.getMetrics(siteId, {
        start: range.start,
        aggregation,
        window: range.window,
      }),
  });

  const checkNow = useMutation({
    mutationFn: () => api.checkNow(siteId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["site", siteId] });
      queryClient.invalidateQueries({ queryKey: ["status", siteId] });
      queryClient.invalidateQueries({ queryKey: ["metrics", siteId] });
    },
  });

  if (site.error) {
    const error = site.error as ApiError;
    return (
      <Panel className="px-6 py-12 text-center">
        <p className="font-display text-xl font-semibold text-fail">{error.message}</p>
        <Link href="/" className="mt-3 inline-block text-sm text-muted underline">
          Back to all targets
        </Link>
      </Panel>
    );
  }

  const target = site.data;
  const meta = target ? STATUS_META[target.last_status] : null;
  const rounds = roundsFromSeries(metrics.data?.series ?? [], 90);

  return (
    <div className="space-y-6">
      <Link href="/" className="eyebrow inline-block hover:text-ink">
        ← All targets
      </Link>

      <section className="panel px-6 py-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <h1 className="font-display text-3xl font-bold tracking-tight">
              {target?.name ?? "…"}
            </h1>
            <p className="tabular mt-1 text-sm text-muted">{target?.fqdn}</p>
            {target && (
              <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2">
                <StatusLabel status={target.last_status} />
                <span className="text-xs text-faint">
                  checked {relativeTime(target.last_checked_at)}
                </span>
                <span className="text-xs text-faint">
                  every {target.check_interval ?? 30}s
                </span>
                {!target.is_active && (
                  <span className="eyebrow rounded-sm bg-sunk px-2 py-0.5">paused</span>
                )}
              </div>
            )}
            {meta && <p className="mt-3 max-w-xl text-sm text-muted">{meta.detail}</p>}
          </div>

          <button
            type="button"
            onClick={() => checkNow.mutate()}
            disabled={checkNow.isPending}
            className="shrink-0 rounded-sm border border-rule bg-sunk px-4 py-2 font-display text-sm font-semibold transition-colors hover:border-rule-strong disabled:opacity-60"
          >
            {checkNow.isPending ? "Checking…" : "Check now"}
          </button>
        </div>

        {checkNow.isError && (
          <p className="mt-3 text-sm text-fail">
            {(checkNow.error as ApiError).message}
          </p>
        )}
      </section>

      <Panel title="Latest reading per probe">
        <ProbeCards
          probes={status.data?.probes ?? {}}
          enabled={target?.enabled_probe_types ?? ["dns", "tcp", "https"]}
        />
      </Panel>

      <Panel
        title="Latency"
        aside={
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex gap-1">
              {RANGES.map((option) => (
                <button
                  key={option.label}
                  type="button"
                  onClick={() => setRange(option)}
                  className={`eyebrow rounded-sm px-2 py-1 transition-colors ${
                    range.label === option.label
                      ? "bg-ink text-surface"
                      : "text-faint hover:text-ink"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <select
              value={aggregation}
              onChange={(event) => setAggregation(event.target.value as Aggregation)}
              aria-label="Aggregation"
              className="eyebrow rounded-sm border border-rule bg-sunk px-2 py-1 outline-none"
            >
              {AGGREGATIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>
        }
      >
        <div className="px-4 pt-4 pb-3">
          {metrics.isLoading ? (
            <p className="py-24 text-center text-sm text-muted">Loading measurements…</p>
          ) : (
            <LatencyChart
              series={metrics.data?.series ?? []}
              field="latency_ms"
              spanHours={range.hours}
            />
          )}
        </div>
      </Panel>

      <Panel title={`Check history · last ${range.label}`}>
        <div className="px-4 py-5">
          <EvidenceStrip rounds={rounds} height={56} fill label="Per-round outcomes" />
          <div className="mt-1.5 flex justify-between">
            <span className="eyebrow">oldest</span>
            <span className="eyebrow">{rounds.length} rounds</span>
            <span className="eyebrow">newest</span>
          </div>
          <p className="mt-4 max-w-2xl text-sm text-muted">
            One bar per round, oldest first. Heal needs the same suspicious signal in
            consecutive rounds before it reports filtering, so a lone spike here means
            far less than a run of them.
          </p>
        </div>
      </Panel>
    </div>
  );
}

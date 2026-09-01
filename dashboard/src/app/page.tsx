"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { GlobalVerdict } from "@/components/GlobalVerdict";
import { Panel } from "@/components/Panel";
import { TargetRow } from "@/components/TargetRow";
import { api } from "@/lib/api";
import type { ApiError } from "@/lib/api";
import { SITE_STATUSES } from "@/lib/types";

type Filter = "all" | "attention" | "healthy";

export default function OverviewPage() {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  const { data, isLoading, error } = useQuery({
    queryKey: ["sites"],
    queryFn: () => api.listSites({ pageSize: 200 }),
  });

  const sites = useMemo(() => data?.items ?? [], [data]);

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return sites.filter((site) => {
      if (needle && !`${site.name} ${site.fqdn}`.toLowerCase().includes(needle)) return false;
      if (filter === "healthy") return site.last_status === "healthy";
      if (filter === "attention") return !["healthy", "unknown"].includes(site.last_status);
      return true;
    });
  }, [sites, search, filter]);

  if (error) {
    const apiError = error as ApiError;
    return (
      <Panel className="px-6 py-10 text-center">
        <p className="font-display text-xl font-semibold text-fail">{apiError.message}</p>
        <p className="mt-2 text-sm text-muted">
          {apiError.detail || "Start the API, then reload this page."}
        </p>
      </Panel>
    );
  }

  return (
    <div className="space-y-6">
      <GlobalVerdict sites={sites} />

      <Panel
        title={`Targets (${visible.length})`}
        aside={
          <div className="flex w-full flex-wrap items-center gap-3 sm:w-auto">
            <div className="flex gap-1">
              {(["all", "attention", "healthy"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setFilter(option)}
                  className={`eyebrow rounded-sm px-2 py-1 transition-colors ${
                    filter === option
                      ? "bg-ink text-surface"
                      : "text-faint hover:text-ink"
                  }`}
                >
                  {option}
                </button>
              ))}
            </div>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Filter by name or FQDN"
              aria-label="Filter targets"
              className="min-w-0 flex-1 rounded-sm border border-rule bg-sunk px-2.5 py-1.5 text-xs outline-none placeholder:text-faint focus:border-suspect sm:w-52 sm:flex-none"
            />
          </div>
        }
      >
        {isLoading && <p className="px-4 py-8 text-sm text-muted">Loading targets…</p>}

        {!isLoading && sites.length === 0 && (
          <div className="px-4 py-12 text-center">
            <p className="font-display text-lg font-semibold">No targets yet</p>
            <p className="mt-1 text-sm text-muted">
              Register an FQDN through the API and Heal starts probing it on the next round.
            </p>
            <code className="tabular mt-4 inline-block rounded-sm bg-sunk px-3 py-2 text-xs text-muted">
              POST /api/v1/sites {"{"}&quot;name&quot;: &quot;ArvanCloud&quot;, &quot;fqdn&quot;:
              &quot;arvancloud.ir&quot;{"}"}
            </code>
          </div>
        )}

        {!isLoading && sites.length > 0 && visible.length === 0 && (
          <p className="px-4 py-10 text-center text-sm text-muted">
            No targets match this filter.
          </p>
        )}

        {visible.map((site) => (
          <TargetRow key={site.id} site={site} />
        ))}
      </Panel>

      <p className="eyebrow text-center">
        {SITE_STATUSES.length} states tracked · refreshed every 15s
      </p>
    </div>
  );
}

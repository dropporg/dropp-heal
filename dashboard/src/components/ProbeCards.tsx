import { latency, relativeTime } from "@/lib/format";
import type { ProbeSnapshot, ProbeType } from "@/lib/types";

/**
 * Per-probe readings side by side. Reading these together is how an operator
 * separates a dead host from a filtered one: DNS resolving while TCP times out
 * is the signal, and no single card shows it.
 */
export function ProbeCards({
  probes,
  enabled,
}: {
  probes: Partial<Record<ProbeType, ProbeSnapshot>>;
  enabled: ProbeType[];
}) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-px bg-rule">
      {enabled.map((probe) => {
        const reading = probes[probe];
        const ok = reading?.success;
        const color =
          ok === undefined
            ? "var(--signal-idle)"
            : ok
              ? "var(--signal-good)"
              : "var(--signal-fail)";
        return (
          <div key={probe} className="bg-surface px-4 py-3">
            <div className="flex items-center justify-between">
              <p className="eyebrow">{probe}</p>
              <span
                aria-hidden
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: color }}
              />
            </div>
            <p className="tabular mt-1.5 text-xl font-semibold" style={{ color }}>
              {reading ? latency(reading.latency_ms) : "—"}
            </p>
            <p className="mt-0.5 text-xs text-faint">
              {reading?.status_code
                ? `HTTP ${reading.status_code}`
                : reading?.packet_loss_percent != null
                  ? `${reading.packet_loss_percent}% loss`
                  : reading
                    ? relativeTime(reading.checked_at)
                    : "not run"}
            </p>
          </div>
        );
      })}
    </div>
  );
}

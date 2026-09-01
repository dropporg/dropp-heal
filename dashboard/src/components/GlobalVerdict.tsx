import { CERTAINTY_COLOR } from "@/lib/status";
import type { Site } from "@/lib/types";

/**
 * The headline answers one question: is anything being blocked right now?
 * Filtering leads because it is the reason Heal exists; plain outages are
 * reported after it, and a quiet network says so in one line.
 */
export function GlobalVerdict({ sites }: { sites: Site[] }) {
  const monitored = sites.filter((site) => site.is_active);
  const suspected = monitored.filter((site) => site.last_status === "suspected_filtered");
  const failing = monitored.filter((site) =>
    ["unreachable", "dns_failed", "timeout", "connection_refused", "tls_failed"].includes(
      site.last_status,
    ),
  );
  const degraded = monitored.filter((site) =>
    ["degraded", "http_error"].includes(site.last_status),
  );
  const waiting = monitored.filter((site) => site.last_status === "unknown");
  const healthy = monitored.length - suspected.length - failing.length - degraded.length - waiting.length;

  let headline: string;
  let tone: keyof typeof CERTAINTY_COLOR;
  let detail: string;

  if (monitored.length === 0) {
    headline = "Nothing is being monitored";
    tone = "unknown";
    detail = "Add a target to start collecting reachability and latency data.";
  } else if (suspected.length > 0) {
    headline = `${suspected.length} ${suspected.length === 1 ? "target looks" : "targets look"} filtered`;
    tone = "suspected";
    detail =
      "Repeated rounds match a filtering pattern. Heal reports this as a suspicion, never a certainty.";
  } else if (failing.length > 0) {
    headline = `${failing.length} ${failing.length === 1 ? "target is" : "targets are"} unreachable`;
    tone = "failed";
    detail = "Connections are failing outright rather than being quietly dropped.";
  } else if (degraded.length > 0) {
    headline = `${degraded.length} ${degraded.length === 1 ? "target is" : "targets are"} degraded`;
    tone = "warning";
    detail = "Reachable, but not every probe is succeeding.";
  } else if (waiting.length === monitored.length) {
    headline = "Waiting for the first round";
    tone = "unknown";
    detail = "The monitoring engine has not reported on these targets yet.";
  } else {
    headline = "Everything is reachable";
    tone = "good";
    detail = `${healthy} of ${monitored.length} targets answering normally.`;
  }

  const counts = [
    { label: "Healthy", value: Math.max(healthy, 0), tone: "good" as const },
    { label: "Degraded", value: degraded.length, tone: "warning" as const },
    { label: "Failing", value: failing.length, tone: "failed" as const },
    { label: "Suspected", value: suspected.length, tone: "suspected" as const },
    { label: "Pending", value: waiting.length, tone: "unknown" as const },
  ];

  return (
    <section className="panel px-6 py-7 sm:px-8">
      <div className="flex flex-col gap-7 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl">
          <p className="eyebrow mb-3">Global status</p>
          <h1
            className="font-display text-4xl leading-[1.05] font-bold tracking-tight sm:text-5xl"
            style={{ color: CERTAINTY_COLOR[tone] }}
          >
            {headline}
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-muted">{detail}</p>
        </div>

        <dl className="grid grid-cols-3 gap-x-8 gap-y-4 sm:grid-cols-5 lg:gap-x-6">
          {counts.map((entry) => (
            <div key={entry.label}>
              <dt className="eyebrow mb-1">{entry.label}</dt>
              <dd
                className="tabular text-2xl font-semibold"
                style={{ color: entry.value > 0 ? CERTAINTY_COLOR[entry.tone] : "var(--ink-faint)" }}
              >
                {entry.value}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

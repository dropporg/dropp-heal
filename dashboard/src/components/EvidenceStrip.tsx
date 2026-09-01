"use client";

import { colorOf } from "@/lib/status";
import type { SiteStatus } from "@/lib/types";

/**
 * One bar per recent check round, oldest to newest.
 *
 * Heal never calls a target filtered on a single failure: it needs the same
 * suspicious signal several rounds running. This strip shows that evidence
 * accumulating, so an operator can tell "one bad round" from "a pattern" at a
 * glance - the distinction the verdict itself hides.
 */
export function EvidenceStrip({
  rounds,
  height = 26,
  label,
  fill = false,
}: {
  rounds: SiteStatus[];
  height?: number;
  label?: string;
  /** Stretch to the container width; otherwise bars keep a fixed hairline width. */
  fill?: boolean;
}) {
  if (rounds.length === 0) {
    return (
      <p className="text-xs text-faint" style={{ lineHeight: `${height}px` }}>
        No rounds recorded yet.
      </p>
    );
  }

  return (
    <div
      className="flex items-end gap-[2px] border-b border-rule"
      style={{ height }}
      aria-label={label ?? `${rounds.length} check rounds`}
      role="img"
    >
      {rounds.map((status, index) => {
        const settled = status === "healthy";
        // Failures stand full height; healthy rounds stay low so the eye is
        // drawn to the exceptions, not the baseline.
        const share = settled ? 0.3 : status === "unknown" ? 0.16 : 1;
        return (
          <span
            key={index}
            title={`${status.replace(/_/g, " ")} · round ${index + 1} of ${rounds.length}`}
            style={{
              background: colorOf(status),
              height: `${share * 100}%`,
              opacity: status === "unknown" ? 0.45 : 1,
            }}
            className={`${fill ? "min-w-[2px] flex-1" : "w-[3px]"} shrink-0 rounded-[1px]`}
          />
        );
      })}
    </div>
  );
}

import { STATUS_META, colorOf } from "@/lib/status";
import type { SiteStatus } from "@/lib/types";

/**
 * A suspicion is drawn hollow and a confirmed failure solid, so the two never
 * read the same from across a room.
 */
export function StatusMark({ status, size = 9 }: { status: SiteStatus; size?: number }) {
  const color = colorOf(status);
  const hollow = status === "suspected_filtered";
  return (
    <span
      aria-hidden
      className="inline-block shrink-0 rounded-full"
      style={{
        width: size,
        height: size,
        background: hollow ? "transparent" : color,
        border: `2px solid ${color}`,
      }}
    />
  );
}

export function StatusLabel({ status }: { status: SiteStatus }) {
  const meta = STATUS_META[status];
  return (
    <span className="inline-flex items-center gap-2">
      <StatusMark status={status} />
      <span className="font-display text-sm font-semibold" style={{ color: colorOf(status) }}>
        {meta.label}
      </span>
    </span>
  );
}

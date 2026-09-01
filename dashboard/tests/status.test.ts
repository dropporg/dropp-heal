import { describe, expect, it } from "vitest";

import { STATUS_META, certaintyOf, colorOf } from "@/lib/status";
import { SITE_STATUSES } from "@/lib/types";

describe("status semantics", () => {
  it("describes every status the API can return", () => {
    for (const status of SITE_STATUSES) {
      expect(STATUS_META[status]?.label).toBeTruthy();
      expect(STATUS_META[status]?.detail).toBeTruthy();
    }
  });

  it("treats a filtering suspicion as its own certainty, not a failure", () => {
    // The backend never claims filtering outright, so the UI must not colour it
    // like a confirmed outage.
    expect(certaintyOf("suspected_filtered")).toBe("suspected");
    expect(colorOf("suspected_filtered")).not.toBe(colorOf("unreachable"));
  });

  it("groups hard failures together", () => {
    for (const status of ["unreachable", "dns_failed", "timeout", "tls_failed"] as const) {
      expect(certaintyOf(status)).toBe("failed");
    }
  });

  it("keeps http errors softer than unreachable hosts", () => {
    expect(certaintyOf("http_error")).toBe("warning");
    expect(certaintyOf("degraded")).toBe("warning");
  });

  it("falls back to unknown for a status it has never seen", () => {
    // A new state added to the API must not crash the dashboard.
    expect(certaintyOf("teapot" as never)).toBe("unknown");
  });
});

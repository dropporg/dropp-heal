import { describe, expect, it, vi } from "vitest";

import { latency, relativeTime } from "@/lib/format";

describe("latency", () => {
  it("keeps sub-100ms readings precise", () => {
    expect(latency(13.24)).toBe("13.2 ms");
  });

  it("rounds readings a person would not compare at decimal precision", () => {
    expect(latency(198.6)).toBe("199 ms");
  });

  it("switches to seconds once milliseconds stop being readable", () => {
    expect(latency(1108)).toBe("1.11 s");
  });

  it("shows a dash rather than zero when nothing was measured", () => {
    expect(latency(null)).toBe("—");
    expect(latency(undefined)).toBe("—");
  });
});

describe("relativeTime", () => {
  it("says never when a target has not been checked", () => {
    expect(relativeTime(null)).toBe("never");
  });

  it("describes recent, minute and hour old checks", () => {
    vi.setSystemTime(new Date("2026-08-30T12:00:00Z"));
    expect(relativeTime("2026-08-30T11:59:58Z")).toBe("just now");
    expect(relativeTime("2026-08-30T11:59:20Z")).toBe("40s ago");
    expect(relativeTime("2026-08-30T11:30:00Z")).toBe("30m ago");
    expect(relativeTime("2026-08-30T09:00:00Z")).toBe("3h ago");
    expect(relativeTime("2026-08-28T12:00:00Z")).toBe("2d ago");
    vi.useRealTimers();
  });
});

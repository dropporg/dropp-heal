import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GlobalVerdict } from "@/components/GlobalVerdict";
import type { Site, SiteStatus } from "@/lib/types";

function site(status: SiteStatus, overrides: Partial<Site> = {}): Site {
  return {
    id: `${status}-${Math.random()}`,
    name: "Target",
    fqdn: "example.test",
    description: null,
    is_active: true,
    check_interval: null,
    timeout: null,
    enabled_probe_types: ["dns", "tcp", "https"],
    http_method: "GET",
    http_path: "/",
    expected_status_codes: [200],
    tcp_ports: [80, 443],
    influxdb_tag: "tag",
    last_status: status,
    last_checked_at: null,
    created_at: "2026-08-30T12:00:00Z",
    updated_at: "2026-08-30T12:00:00Z",
    ...overrides,
  };
}

describe("GlobalVerdict", () => {
  it("invites the first target when nothing is monitored", () => {
    render(<GlobalVerdict sites={[]} />);
    expect(screen.getByText("Nothing is being monitored")).toBeInTheDocument();
  });

  it("says so plainly when every target answers", () => {
    render(<GlobalVerdict sites={[site("healthy"), site("healthy")]} />);
    expect(screen.getByText("Everything is reachable")).toBeInTheDocument();
  });

  it("leads with filtering, because that is what Heal exists to catch", () => {
    // An outage and a suspected block at the same time: the block wins the
    // headline, since a plain outage is the less surprising finding.
    render(<GlobalVerdict sites={[site("suspected_filtered"), site("unreachable")]} />);
    expect(screen.getByText("1 target looks filtered")).toBeInTheDocument();
  });

  it("never states filtering as fact", () => {
    render(<GlobalVerdict sites={[site("suspected_filtered")]} />);
    expect(screen.getByText(/never a certainty/i)).toBeInTheDocument();
  });

  it("reports unreachable targets when nothing looks filtered", () => {
    render(<GlobalVerdict sites={[site("unreachable"), site("dns_failed"), site("healthy")]} />);
    expect(screen.getByText("2 targets are unreachable")).toBeInTheDocument();
  });

  it("counts each state separately", () => {
    render(
      <GlobalVerdict
        sites={[site("healthy"), site("degraded"), site("timeout"), site("suspected_filtered")]}
      />,
    );
    const counts = ["Healthy", "Degraded", "Failing", "Suspected", "Pending"].map(
      (label) => screen.getByText(label).nextElementSibling?.textContent,
    );
    expect(counts).toEqual(["1", "1", "1", "1", "0"]);
  });

  it("ignores paused targets, which are not being checked", () => {
    render(<GlobalVerdict sites={[site("healthy"), site("unreachable", { is_active: false })]} />);
    expect(screen.getByText("Everything is reachable")).toBeInTheDocument();
  });

  it("explains the wait before the first round rather than claiming health", () => {
    render(<GlobalVerdict sites={[site("unknown"), site("unknown")]} />);
    expect(screen.getByText("Waiting for the first round")).toBeInTheDocument();
  });
});

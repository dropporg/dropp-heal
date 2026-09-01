import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProbeCards } from "@/components/ProbeCards";

describe("ProbeCards", () => {
  it("shows a card for every enabled probe, even one that has not run", () => {
    render(<ProbeCards probes={{}} enabled={["dns", "tcp", "https"]} />);

    for (const probe of ["dns", "tcp", "https"]) {
      expect(screen.getByText(probe)).toBeInTheDocument();
    }
    expect(screen.getAllByText("not run")).toHaveLength(3);
  });

  it("reports the latest latency and http status", () => {
    render(
      <ProbeCards
        probes={{
          https: {
            success: true,
            latency_ms: 86.1,
            status_code: 200,
            packet_loss_percent: null,
            checked_at: "2026-08-30T12:00:00Z",
          },
        }}
        enabled={["https"]}
      />,
    );

    expect(screen.getByText("86.1 ms")).toBeInTheDocument();
    expect(screen.getByText("HTTP 200")).toBeInTheDocument();
  });

  it("shows packet loss for icmp, which has no status code", () => {
    render(
      <ProbeCards
        probes={{
          icmp: {
            success: true,
            latency_ms: 12,
            status_code: null,
            packet_loss_percent: 25,
            checked_at: "2026-08-30T12:00:00Z",
          },
        }}
        enabled={["icmp"]}
      />,
    );

    expect(screen.getByText("25% loss")).toBeInTheDocument();
  });

  it("does not render probes the target has disabled", () => {
    render(<ProbeCards probes={{}} enabled={["dns"]} />);
    expect(screen.queryByText("icmp")).not.toBeInTheDocument();
  });
});

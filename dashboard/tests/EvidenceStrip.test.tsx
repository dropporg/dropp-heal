import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EvidenceStrip } from "@/components/EvidenceStrip";
import { StatusMark } from "@/components/StatusMark";

describe("EvidenceStrip", () => {
  it("says nothing has been recorded rather than drawing an empty chart", () => {
    render(<EvidenceStrip rounds={[]} />);
    expect(screen.getByText("No rounds recorded yet.")).toBeInTheDocument();
  });

  it("draws one bar per round", () => {
    const { container } = render(
      <EvidenceStrip rounds={["healthy", "timeout", "healthy"]} label="history" />,
    );
    expect(container.querySelectorAll("span")).toHaveLength(3);
  });

  it("stands failures full height and keeps healthy rounds low", () => {
    // The eye should land on the exceptions, not the baseline.
    const { container } = render(<EvidenceStrip rounds={["healthy", "timeout"]} />);
    const [healthy, failed] = [...container.querySelectorAll("span")];
    expect(failed.style.height).toBe("100%");
    expect(parseFloat(healthy.style.height)).toBeLessThan(100);
  });

  it("numbers each round in its tooltip so a run can be counted", () => {
    render(<EvidenceStrip rounds={["timeout", "timeout"]} />);
    expect(screen.getByTitle("timeout · round 2 of 2")).toBeInTheDocument();
  });

  it("exposes the history to assistive technology", () => {
    render(<EvidenceStrip rounds={["healthy"]} label="Google check history" />);
    expect(screen.getByRole("img", { name: "Google check history" })).toBeInTheDocument();
  });
});

describe("StatusMark", () => {
  it("draws a suspicion hollow and a confirmed failure solid", () => {
    const { container: suspected } = render(<StatusMark status="suspected_filtered" />);
    const { container: failed } = render(<StatusMark status="unreachable" />);

    expect(suspected.firstElementChild).toHaveStyle({ background: "transparent" });
    expect(failed.firstElementChild).not.toHaveStyle({ background: "transparent" });
  });
});

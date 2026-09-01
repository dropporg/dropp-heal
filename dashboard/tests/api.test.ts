import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "@/lib/api";
import type { Envelope, Site } from "@/lib/types";

function respond<T>(result: T, init: { status?: number; code?: number; detail?: string } = {}) {
  const body: Envelope<T> = {
    result,
    status: { code: init.code ?? 100, message: "OK" },
    _metadata: init.detail ?? "",
  };
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status: init.status ?? 200,
      headers: { "content-type": "application/json" },
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("unwraps the envelope and returns the result", async () => {
    const site = { id: "abc", fqdn: "arvancloud.ir" } as Site;
    vi.stubGlobal("fetch", vi.fn<typeof fetch>(() => respond(site)));

    await expect(api.getSite("abc")).resolves.toEqual(site);
  });

  it("raises the application code, which is finer grained than the http status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => respond(null, { status: 409, code: 105, detail: "arvancloud.ir" })),
    );

    const error = await api.createSite({ name: "x", fqdn: "arvancloud.ir" }).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe(105);
    expect(error.detail).toBe("arvancloud.ir");
  });

  it("reports an unreachable API rather than throwing a fetch error", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>(() => Promise.reject(new TypeError("failed to fetch"))));

    const error = await api.listSites().catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).toBe("Cannot reach the Heal API");
  });

  it("passes list filters through as query parameters", async () => {
    const fetchMock = vi.fn<typeof fetch>(() => respond({ items: [], total: 0, page: 1, page_size: 50 }));
    vi.stubGlobal("fetch", fetchMock);

    await api.listSites({ search: "arvan", status: "healthy", isActive: true, page: 2 });

    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain("search=arvan");
    expect(url).toContain("status=healthy");
    expect(url).toContain("is_active=true");
    expect(url).toContain("page=2");
  });

  it("builds the metrics query the graphs depend on", async () => {
    const fetchMock = vi.fn<typeof fetch>(() => respond({ series: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await api.getMetrics("abc", {
      start: "-2d",
      aggregation: "p95",
      window: "1h",
      probeType: "https",
      field: "latency_ms",
    });

    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain("start=-2d");
    expect(url).toContain("aggregation=p95");
    expect(url).toContain("window=1h");
    expect(url).toContain("probe_type=https");
    expect(url).toContain("field=latency_ms");
  });

  it("enables and disables through the matching endpoints", async () => {
    const fetchMock = vi.fn<typeof fetch>(() => respond({} as Site));
    vi.stubGlobal("fetch", fetchMock);

    await api.setActive("abc", true);
    expect(String(fetchMock.mock.calls[0][0])).toContain("/enable");

    await api.setActive("abc", false);
    expect(String(fetchMock.mock.calls[1][0])).toContain("/disable");
  });
});

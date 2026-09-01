import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DELETE, GET, POST } from "@/app/api/[...path]/route";

const context = (path: string[]) => ({ params: Promise.resolve({ path }) });

beforeEach(() => {
  process.env.HEAL_API_URL = "http://api.internal:8000";
});

afterEach(() => {
  vi.unstubAllGlobals();
  delete process.env.HEAL_API_URL;
});

describe("api proxy", () => {
  it("forwards to the API named at request time, not at build time", async () => {
    // A build-time value would pin one cluster's address into the image.
    const fetchMock = vi.fn<typeof fetch>(() => Promise.resolve(new Response("{}", { status: 200 })));
    vi.stubGlobal("fetch", fetchMock);

    await GET(new NextRequest("http://dashboard.test/api/v1/sites"), context(["v1", "sites"]));

    expect(String(fetchMock.mock.calls[0][0])).toBe("http://api.internal:8000/api/v1/sites");
  });

  it("keeps the query string, which carries the metrics range", async () => {
    const fetchMock = vi.fn<typeof fetch>(() => Promise.resolve(new Response("{}", { status: 200 })));
    vi.stubGlobal("fetch", fetchMock);

    await GET(
      new NextRequest("http://dashboard.test/api/v1/sites/abc/metrics?start=-2d&aggregation=p95"),
      context(["v1", "sites", "abc", "metrics"]),
    );

    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain("start=-2d");
    expect(url).toContain("aggregation=p95");
  });

  it("passes a request body through on writes", async () => {
    const fetchMock = vi.fn<typeof fetch>(() => Promise.resolve(new Response("{}", { status: 201 })));
    vi.stubGlobal("fetch", fetchMock);

    await POST(
      new NextRequest("http://dashboard.test/api/v1/sites", {
        method: "POST",
        body: JSON.stringify({ fqdn: "arvancloud.ir" }),
        headers: { "content-type": "application/json" },
      }),
      context(["v1", "sites"]),
    );

    const init = fetchMock.mock.calls[0][1]!;
    expect(init.method).toBe("POST");
    expect(init.body).toContain("arvancloud.ir");
  });

  it("relays the API status code instead of flattening errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response("{}", { status: 404 }))),
    );

    const response = await DELETE(
      new NextRequest("http://dashboard.test/api/v1/sites/missing", { method: "DELETE" }),
      context(["v1", "sites", "missing"]),
    );
    expect(response.status).toBe(404);
  });

  it("answers in the API's own envelope when the API cannot be reached", async () => {
    // The client renders any envelope, so an unreachable API still shows a
    // readable message instead of a blank screen.
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("connect ECONNREFUSED"))),
    );

    const response = await GET(
      new NextRequest("http://dashboard.test/api/v1/sites"),
      context(["v1", "sites"]),
    );
    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toMatchObject({
      result: null,
      status: { code: 103 },
    });
  });
});

import { NextRequest, NextResponse } from "next/server";

/**
 * Server-side proxy to the Heal API.
 *
 * The browser only ever calls this origin, so there is no CORS to configure and
 * the API needs no public route. HEAL_API_URL is read per request rather than
 * through next.config rewrites, whose destinations are resolved at build time
 * and would bake one cluster's address into the image.
 */
export const dynamic = "force-dynamic";

const target = () => process.env.HEAL_API_URL ?? "http://localhost:8000";

async function proxy(request: NextRequest, path: string[]) {
  const url = new URL(`/api/${path.join("/")}`, target());
  url.search = request.nextUrl.search;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);

  let body: string | undefined;
  if (request.method !== "GET" && request.method !== "DELETE") {
    body = await request.text();
  }

  try {
    const response = await fetch(url, {
      method: request.method,
      headers,
      body: body || undefined,
      cache: "no-store",
    });
    const payload = await response.text();
    return new NextResponse(payload, {
      status: response.status,
      headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    // Shaped like the API's own envelope so the client renders it normally.
    return NextResponse.json(
      {
        result: null,
        status: { code: 103, message: "Cannot reach the Heal API" },
        _metadata: url.origin,
      },
      { status: 503 },
    );
  }
}

type Context = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, context: Context) {
  return proxy(request, (await context.params).path);
}
export async function POST(request: NextRequest, context: Context) {
  return proxy(request, (await context.params).path);
}
export async function PATCH(request: NextRequest, context: Context) {
  return proxy(request, (await context.params).path);
}
export async function DELETE(request: NextRequest, context: Context) {
  return proxy(request, (await context.params).path);
}

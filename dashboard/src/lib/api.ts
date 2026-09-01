import type {
  Aggregation,
  CheckResult,
  Envelope,
  MetricsRead,
  ProbeType,
  Site,
  SiteList,
  SiteStatus,
  SiteStatusRead,
} from "./types";

/**
 * Empty means same-origin, which the Next rewrite proxies to the API. Set
 * NEXT_PUBLIC_API_URL only to bypass the proxy and call the API directly, which
 * then needs the dashboard's origin in HEAL_API_CORS_ORIGINS.
 */
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

/** Carries the application code, which is more specific than the HTTP status. */
export class ApiError extends Error {
  constructor(
    readonly code: number,
    message: string,
    readonly detail: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "content-type": "application/json", ...init?.headers },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "Cannot reach the Heal API", `Tried ${BASE || "this origin"}${path}`);
  }

  const body = (await response.json().catch(() => null)) as Envelope<T> | null;
  if (!body) {
    throw new ApiError(response.status, "The API returned an unreadable response", "");
  }
  if (!response.ok) {
    throw new ApiError(body.status.code, body.status.message, body._metadata);
  }
  return body.result;
}

export interface SiteQuery {
  page?: number;
  pageSize?: number;
  status?: SiteStatus;
  isActive?: boolean;
  search?: string;
}

export const api = {
  listSites(query: SiteQuery = {}): Promise<SiteList> {
    const params = new URLSearchParams();
    params.set("page", String(query.page ?? 1));
    params.set("page_size", String(query.pageSize ?? 100));
    if (query.status) params.set("status", query.status);
    if (query.isActive !== undefined) params.set("is_active", String(query.isActive));
    if (query.search) params.set("search", query.search);
    return request<SiteList>(`/api/v1/sites?${params}`);
  },

  getSite(siteId: string): Promise<Site> {
    return request<Site>(`/api/v1/sites/${siteId}`);
  },

  getStatus(siteId: string): Promise<SiteStatusRead> {
    return request<SiteStatusRead>(`/api/v1/sites/${siteId}/status`);
  },

  getMetrics(
    siteId: string,
    options: {
      start: string;
      end?: string;
      probeType?: ProbeType;
      field?: string;
      aggregation?: Aggregation;
      window?: string;
    },
  ): Promise<MetricsRead> {
    const params = new URLSearchParams({ start: options.start });
    if (options.end) params.set("end", options.end);
    if (options.probeType) params.set("probe_type", options.probeType);
    if (options.field) params.set("field", options.field);
    if (options.aggregation) params.set("aggregation", options.aggregation);
    if (options.window) params.set("window", options.window);
    return request<MetricsRead>(`/api/v1/sites/${siteId}/metrics?${params}`);
  },

  checkNow(siteId: string): Promise<CheckResult> {
    return request<CheckResult>(`/api/v1/sites/${siteId}/check`, { method: "POST" });
  },

  createSite(payload: { name: string; fqdn: string }): Promise<Site> {
    return request<Site>("/api/v1/sites", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  setActive(siteId: string, active: boolean): Promise<Site> {
    return request<Site>(`/api/v1/sites/${siteId}/${active ? "enable" : "disable"}`, {
      method: "POST",
    });
  },

  deleteSite(siteId: string): Promise<{ deleted: string }> {
    return request<{ deleted: string }>(`/api/v1/sites/${siteId}`, { method: "DELETE" });
  },
};

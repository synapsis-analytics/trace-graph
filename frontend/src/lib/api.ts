/**
 * Thin API client for the TRACE HTTP contract (PLAN.md §4).
 * All URLs are relative: in production FastAPI serves the SPA from the same origin,
 * in dev Vite proxies /api and /health to the backend or the mock.
 */
import { accessKeyStore } from "./storage";
import type {
  AskResponse,
  Claim,
  ClaimList,
  CoverageResponse,
  GraphPayload,
  Health,
  Lens,
  ObjectDetail,
  ObjectList,
  PathResponse,
  Stats,
  TraceObject,
  ApiError,
  Attrs,
} from "./types";

export class HttpError extends Error implements ApiError {
  status: number;
  detail?: string;
  constructor(status: number, message: string, detail?: string) {
    super(message);
    this.name = "HttpError";
    this.status = status;
    this.detail = detail;
  }
}

type Query = Record<string, string | number | boolean | undefined | null | string[]>;

export function qs(params: Query): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) {
      if (v.length === 0) continue;
      sp.set(k, v.join(","));
    } else {
      sp.set(k, String(v));
    }
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

async function request<T>(
  path: string,
  init?: RequestInit & { auth?: boolean },
): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (init?.auth) {
    const key = accessKeyStore.get();
    if (key) headers.set("X-Access-Key", key);
  }
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers });
  } catch (e) {
    throw new HttpError(0, "Cannot reach the TRACE API", e instanceof Error ? e.message : undefined);
  }
  if (!res.ok) {
    let detail: string | undefined;
    try {
      const body = (await res.json()) as { detail?: unknown; message?: unknown };
      const d = body.detail ?? body.message;
      detail = typeof d === "string" ? d : d ? JSON.stringify(d) : undefined;
    } catch {
      detail = undefined;
    }
    throw new HttpError(res.status, detail || `${res.status} ${res.statusText}`, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export interface ObjectsParams {
  type?: string;
  q?: string;
  limit?: number;
  offset?: number;
  band?: string;
  source?: string;
}

export interface NeighbourhoodParams {
  depth?: number;
  lens?: string;
  predicates?: string[];
  types?: string[];
  limit?: number;
}

export interface GraphParams {
  lens?: string;
  types?: string[];
  predicates?: string[];
  limit?: number;
}

export interface ClaimsParams {
  status?: string;
  band?: string;
  subject?: string;
  kind?: string;
  limit?: number;
  offset?: number;
}

export interface NewClaim {
  kind: string;
  subject?: string;
  predicate?: string;
  object?: string;
  payload?: Attrs;
  attested_by?: string;
  provenance?: string;
  evidence?: { kind: string; value: string }[];
}

export const api = {
  health: () => request<Health>("/health"),
  stats: () => request<Stats>("/api/stats"),
  lenses: () => request<{ lenses: Lens[] } | Lens[]>("/api/lenses"),
  objects: (p: ObjectsParams) => request<ObjectList>(`/api/objects${qs({ ...p })}`),
  object: (id: string) => request<ObjectDetail>(`/api/objects/${encodeURIComponent(id)}`),
  neighbourhood: (id: string, p: NeighbourhoodParams) =>
    request<GraphPayload>(`/api/objects/${encodeURIComponent(id)}/neighbourhood${qs({ ...p })}`),
  graph: (p: GraphParams) => request<GraphPayload>(`/api/graph${qs({ ...p })}`),
  path: (from: string, to: string, lens?: string, maxLen = 6) =>
    request<PathResponse>(`/api/path${qs({ from, to, lens, max_len: maxLen })}`),
  resolveId: (scheme: string, value: string) =>
    request<TraceObject>(`/api/resolve-id${qs({ scheme, value })}`),
  coverage: (layer?: number | string, group?: string) =>
    request<CoverageResponse>(`/api/coverage${qs({ layer, group })}`),
  claims: (p: ClaimsParams) => request<ClaimList>(`/api/claims${qs({ ...p })}`),
  claim: (id: string) => request<Claim>(`/api/claims/${encodeURIComponent(id)}`),
  appendClaim: (claim: NewClaim, dryRun = false) =>
    request<Claim>(`/api/claims${qs({ dry_run: dryRun ? 1 : undefined })}`, {
      method: "POST",
      body: JSON.stringify(claim),
      auth: true,
    }),
  decideClaim: (id: string, decision: "accept" | "reject", by: string, note?: string) =>
    request<Claim>(`/api/claims/${encodeURIComponent(id)}/decide`, {
      method: "POST",
      body: JSON.stringify({ decision, by, note }),
      auth: true,
    }),
  ask: (question: string) =>
    request<AskResponse>("/api/ask", { method: "POST", body: JSON.stringify({ question }) }),
};

/** /api/lenses may return a bare array or {lenses: [...]}; normalise. */
export function unwrapLenses(payload: { lenses: Lens[] } | Lens[] | undefined): Lens[] {
  if (!payload) return [];
  if (Array.isArray(payload)) return payload;
  return Array.isArray(payload.lenses) ? payload.lenses : [];
}

/**
 * Lens logic (PLAN.md §3.6). A lens is a named set of allowed path patterns, e.g.
 *   ["result","CONTRIBUTES_TO","hlo","PART_OF","aow","PART_OF","program"]
 * Odd positions are predicates, even positions are object types. From that we derive
 * the set of types and predicates a lens admits, plus the typed triples it allows, so
 * the UI can filter a graph payload exactly the way the API would.
 *
 * Jose's granularity concern: an edge is only kept if the *triple* (subject type,
 * predicate, object type) appears in one of the lens paths — that is what stops a
 * "money" question from walking result → country.
 */
import type { GraphEdge, GraphNode, GraphPayload, Lens } from "./types";

export interface LensRules {
  types: Set<string>;
  predicates: Set<string>;
  triples: Set<string>;
}

const tripleKey = (s: string, p: string, o: string) => `${s}|${p}|${o}`;

export function lensRules(lens: Lens | undefined): LensRules | null {
  if (!lens) return null;
  const types = new Set<string>(lens.types ?? []);
  const predicates = new Set<string>(lens.predicates ?? []);
  const triples = new Set<string>();
  for (const path of lens.paths ?? []) {
    for (let i = 0; i < path.length; i += 2) {
      const t = path[i];
      if (t) types.add(t);
      const p = path[i + 1];
      const o = path[i + 2];
      if (p && o) {
        predicates.add(p);
        // Lens paths are written in reading order; links are directed subject → object,
        // but a path may traverse a link backwards, so both directions are admitted.
        triples.add(tripleKey(t, p, o));
        triples.add(tripleKey(o, p, t));
      }
    }
  }
  if (types.size === 0 && predicates.size === 0) return null;
  return { types, predicates, triples };
}

export interface FilterOptions {
  lens?: Lens;
  /** Explicit type chips selected in the UI (empty = all). */
  types?: string[];
  /** Explicit predicate chips selected in the UI (empty = all). */
  predicates?: string[];
  /** Keep nodes that end up with no edges (default true). */
  keepIsolated?: boolean;
  /** Drop nodes/edges below this QA band. */
  minBand?: "high" | "medium" | "low";
}

const BAND_RANK: Record<string, number> = { low: 0, medium: 1, high: 2 };

export function bandAtLeast(band: string | undefined, min: string | undefined): boolean {
  if (!min) return true;
  const b = BAND_RANK[band ?? "high"] ?? 2;
  return b >= (BAND_RANK[min] ?? 0);
}

/**
 * Filter a graph payload by lens + explicit chips. Edges whose endpoints were removed
 * are dropped; nodes are kept even when isolated unless `keepIsolated` is false.
 */
export function filterGraph(payload: GraphPayload, opts: FilterOptions = {}): GraphPayload {
  const rules = lensRules(opts.lens);
  const typeChips = new Set(opts.types ?? []);
  const predChips = new Set(opts.predicates ?? []);

  const nodeOk = (n: GraphNode): boolean => {
    if (!bandAtLeast(n.band, opts.minBand)) return false;
    if (typeChips.size > 0 && !typeChips.has(n.type)) return false;
    if (rules && rules.types.size > 0 && !rules.types.has(n.type)) return false;
    return true;
  };

  const nodes = payload.nodes.filter(nodeOk);
  const byId = new Map(nodes.map((n) => [n.id, n]));

  const edgeOk = (e: GraphEdge): boolean => {
    const s = byId.get(e.source);
    const t = byId.get(e.target);
    if (!s || !t) return false;
    if (predChips.size > 0 && !predChips.has(e.predicate)) return false;
    if (rules) {
      if (rules.predicates.size > 0 && !rules.predicates.has(e.predicate)) return false;
      if (rules.triples.size > 0 && !rules.triples.has(tripleKey(s.type, e.predicate, t.type))) return false;
    }
    return true;
  };

  const edges = payload.edges.filter(edgeOk);

  if (opts.keepIsolated === false) {
    const touched = new Set<string>();
    for (const e of edges) {
      touched.add(e.source);
      touched.add(e.target);
    }
    return { nodes: nodes.filter((n) => touched.has(n.id)), edges, truncated: payload.truncated };
  }
  return { nodes, edges, truncated: payload.truncated };
}

/** Merge a second payload into the first (used by double-click "expand neighbourhood"). */
export function mergePayloads(a: GraphPayload, b: GraphPayload): GraphPayload {
  const nodes = new Map<string, GraphNode>();
  for (const n of a.nodes) nodes.set(n.id, n);
  for (const n of b.nodes) nodes.set(n.id, { ...nodes.get(n.id), ...n });
  const edges = new Map<string, GraphEdge>();
  for (const e of a.edges) edges.set(e.id, e);
  for (const e of b.edges) edges.set(e.id, e);
  return {
    nodes: [...nodes.values()],
    edges: [...edges.values()],
    truncated: Boolean(a.truncated || b.truncated),
  };
}

export function countByType(nodes: GraphNode[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const n of nodes) out[n.type] = (out[n.type] ?? 0) + 1;
  return out;
}

export function countByPredicate(edges: GraphEdge[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const e of edges) out[e.predicate] = (out[e.predicate] ?? 0) + 1;
  return out;
}

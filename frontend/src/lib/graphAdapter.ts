/**
 * API JSON → graphology. The only place that knows both shapes.
 * Robustness rules (the API is young and fields go missing):
 *  - a node without an id is dropped; a node without a label falls back to its id;
 *  - an edge pointing at a node we do not have is dropped (no phantom nodes);
 *  - duplicate ids win last-write, duplicate edges are ignored (multi=false);
 *  - x/y are seeded on a deterministic circle so a layout can start from anywhere.
 */
import Graph, { UndirectedGraph } from "graphology";
import forceAtlas2 from "graphology-layout-forceatlas2";
import louvain from "graphology-communities-louvain";
import { typeStyle, bandStyle, communityColor } from "./theme";
import type { Attrs, GraphEdge, GraphNode, GraphPayload } from "./types";

export interface NodeAttributes extends Attrs {
  label: string;
  nodeType: string;
  x: number;
  y: number;
  size: number;
  color: string;
  baseColor: string;
  band: string;
  opacity: number;
  degree: number;
  community?: number;
  raw: GraphNode;
  [key: string]: unknown;
}

export interface EdgeAttributes extends Attrs {
  predicate: string;
  label: string;
  size: number;
  color: string;
  edgeId: string;
  raw: GraphEdge;
  [key: string]: unknown;
}

export type TraceGraph = Graph<NodeAttributes, EdgeAttributes>;

export interface BuildOptions {
  /** Node radius range in graph units. */
  minSize?: number;
  maxSize?: number;
  /** Seed radius for the initial circular placement. */
  radius?: number;
}

function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h);
}

export function isValidNode(n: Partial<GraphNode> | null | undefined): n is GraphNode {
  return Boolean(n && typeof n.id === "string" && n.id.length > 0);
}

/** Build a graphology graph from an API payload. Never throws on bad data. */
export function buildGraph(payload: GraphPayload | undefined, opts: BuildOptions = {}): TraceGraph {
  const minSize = opts.minSize ?? 3;
  const maxSize = opts.maxSize ?? 16;
  const radius = opts.radius ?? 100;
  const graph: TraceGraph = new Graph<NodeAttributes, EdgeAttributes>({
    type: "directed",
    multi: false,
    allowSelfLoops: false,
  });
  if (!payload) return graph;

  const nodes = (payload.nodes ?? []).filter(isValidNode);
  const total = Math.max(nodes.length, 1);

  nodes.forEach((n, i) => {
    const style = typeStyle(n.type);
    const band = n.band ?? "high";
    const angle = (2 * Math.PI * ((i + hash(n.id) % 7) % total)) / total;
    const jitter = (hash(n.id) % 100) / 100;
    const attrs: NodeAttributes = {
      label: n.label && n.label.trim() ? n.label : n.id,
      nodeType: n.type ?? "unknown",
      x: Math.cos(angle) * radius * (0.6 + 0.4 * jitter),
      y: Math.sin(angle) * radius * (0.6 + 0.4 * jitter),
      size: clamp(n.size ?? style.weight, minSize, maxSize),
      color: style.color,
      baseColor: style.color,
      band,
      opacity: bandStyle(band).opacity,
      degree: 0,
      raw: n,
    };
    graph.mergeNode(n.id, attrs);
  });

  for (const e of payload.edges ?? []) {
    if (!e || typeof e.source !== "string" || typeof e.target !== "string") continue;
    if (e.source === e.target) continue;
    if (!graph.hasNode(e.source) || !graph.hasNode(e.target)) continue;
    if (graph.hasEdge(e.source, e.target)) continue;
    graph.addDirectedEdge(e.source, e.target, {
      predicate: e.predicate ?? "RELATED",
      label: (e.predicate ?? "related").toLowerCase().replace(/_/g, " "),
      size: 1,
      color: "rgba(100,116,139,0.35)",
      edgeId: e.id ?? `${e.source}->${e.target}`,
      raw: e,
    });
  }

  // Degree-aware sizing: keeps hubs readable without letting them dominate.
  let maxDegree = 1;
  graph.forEachNode((id) => {
    const d = graph.degree(id);
    if (d > maxDegree) maxDegree = d;
  });
  graph.forEachNode((id, attr) => {
    const d = graph.degree(id);
    const boost = Math.sqrt(d / maxDegree);
    graph.setNodeAttribute(id, "degree", d);
    graph.setNodeAttribute(id, "size", clamp(attr.size + boost * 6, minSize, maxSize));
  });

  return graph;
}

export function clamp(v: number, lo: number, hi: number): number {
  if (!Number.isFinite(v)) return lo;
  return Math.min(hi, Math.max(lo, v));
}

/** Assign Louvain communities and colour nodes by community. Returns the community count. */
export function applyCommunities(graph: TraceGraph): number {
  if (graph.order === 0 || graph.size === 0) return 0;
  try {
    // Louvain needs an undirected view; build one instead of mutating the rendered graph.
    const undirected = new UndirectedGraph();
    graph.forEachNode((id) => undirected.addNode(id));
    graph.forEachEdge((_e, _attr, source, target) => {
      if (source !== target && !undirected.hasEdge(source, target)) undirected.addEdge(source, target);
    });
    const communities = louvain(undirected as unknown as Graph);
    const seen = new Set<number>();
    graph.forEachNode((id) => {
      const c = Number(communities[id] ?? 0);
      seen.add(c);
      graph.setNodeAttribute(id, "community", c);
      graph.setNodeAttribute(id, "color", communityColor(c));
    });
    return seen.size;
  } catch {
    return 0;
  }
}

/** Restore type colouring after community mode is switched off. */
export function applyTypeColours(graph: TraceGraph): void {
  graph.forEachNode((id, attr) => {
    graph.setNodeAttribute(id, "color", attr.baseColor);
  });
}

export function circularLayout(graph: TraceGraph, radius = 120): void {
  const n = Math.max(graph.order, 1);
  let i = 0;
  graph.forEachNode((id) => {
    const angle = (2 * Math.PI * i) / n;
    graph.setNodeAttribute(id, "x", Math.cos(angle) * radius);
    graph.setNodeAttribute(id, "y", Math.sin(angle) * radius);
    i += 1;
  });
}

export function forceAtlasSettings(graph: TraceGraph) {
  const inferred = forceAtlas2.inferSettings(graph);
  return { ...inferred, adjustSizes: true, gravity: 0.6, slowDown: 5 + Math.log(graph.order + 2) };
}

/** Synchronous ForceAtlas2 pass — used for the initial layout of small graphs and in tests. */
export function runForceAtlas(graph: TraceGraph, iterations = 120): void {
  if (graph.order === 0) return;
  forceAtlas2.assign(graph, { iterations, settings: forceAtlasSettings(graph) });
}

/** Neighbour ids (both directions) of a node — used for hover highlighting. */
export function neighbourSet(graph: TraceGraph, id: string): Set<string> {
  const set = new Set<string>();
  if (!graph.hasNode(id)) return set;
  set.add(id);
  graph.forEachNeighbor(id, (nb) => set.add(nb));
  return set;
}

/** Summary used by the left rail counters. */
export function graphSummary(graph: TraceGraph) {
  const byType: Record<string, number> = {};
  graph.forEachNode((_id, attr) => {
    byType[attr.nodeType] = (byType[attr.nodeType] ?? 0) + 1;
  });
  const byPredicate: Record<string, number> = {};
  graph.forEachEdge((_id, attr) => {
    byPredicate[attr.predicate] = (byPredicate[attr.predicate] ?? 0) + 1;
  });
  return { order: graph.order, size: graph.size, byType, byPredicate };
}

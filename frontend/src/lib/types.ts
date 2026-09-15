/**
 * API boundary types — mirror PLAN.md §3/§4 (CONTRACT).
 * Everything the backend may omit is optional here: the UI must survive missing fields.
 */

export const OBJECT_TYPES = [
  "program",
  "aow",
  "hlo",
  "indicator",
  "outcome",
  "result",
  "kp",
  "innovation",
  "institution",
  "country",
  "region",
  "project",
  "melia_study",
  "concept",
  "person",
  "document",
] as const;

export type ObjectType = (typeof OBJECT_TYPES)[number];

export const PREDICATES = [
  "PART_OF",
  "CONTRIBUTES_TO",
  "REPORTED_UNDER",
  "PRODUCED_BY",
  "WITH_PARTNER",
  "LOCATED_IN",
  "EVIDENCED_BY",
  "SAME_AS",
  "DESCRIBES",
  "FUNDED_BY",
  "STUDIED_BY",
  "SYNERGY_WITH",
  "TAGGED_WITH",
  "BROADER",
  "CANDIDATE_FOR",
  "AUTHORED_BY",
] as const;

export type Predicate = (typeof PREDICATES)[number];

export type Band = "high" | "medium" | "low";

/** Free-form attribute bag coming from the API. `unknown` keeps `any` out of the app. */
export type Attrs = Record<string, unknown>;

export interface AltId {
  scheme: string;
  value: string;
}

export interface SourceRef {
  system?: string;
  ref?: string;
  snapshot?: string;
}

export interface QaCheck {
  name: string;
  ok: boolean;
  note?: string;
}

export interface Qa {
  band?: Band;
  score?: number;
  checks?: QaCheck[];
  status?: "accepted" | "review" | "rejected";
  decided_by?: string | null;
  decided_at?: string | null;
}

/** node = {id, type, label, size?, band?, attrs} — graph payload contract. */
export interface GraphNode {
  id: string;
  type: string;
  label: string;
  size?: number;
  band?: Band;
  attrs?: Attrs;
}

/** edge = {id, source, target, predicate, attrs} — graph payload contract. */
export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  predicate: string;
  attrs?: Attrs;
}

export interface GraphPayload {
  nodes: GraphNode[];
  edges: GraphEdge[];
  truncated?: boolean;
}

export interface TraceObject {
  id: string;
  type: string;
  label: string;
  description?: string;
  attrs?: Attrs;
  alt_ids?: AltId[];
  source?: SourceRef;
  created_at?: string;
  updated_at?: string;
  claim_count?: number;
  qa?: Qa;
}

export interface LinkRef {
  id: string;
  predicate: string;
  subject?: string;
  object?: string;
  /** The other end, denormalised by the API for display. */
  neighbour?: { id: string; label?: string; type?: string };
  attrs?: Attrs;
  qa?: Qa;
}

export interface Tag {
  id: string;
  label: string;
  layer?: number | string;
  via?: string;
  confidence?: number;
}

export interface Claim {
  id: string;
  kind: string;
  subject?: string;
  predicate?: string;
  object?: string;
  payload?: Attrs;
  attested_by?: string;
  provenance?: "harvested" | "recorded" | "signed";
  signature?: string | null;
  evidence?: { kind: string; value: string }[];
  taxonomy_version?: string;
  source?: SourceRef;
  created_at?: string;
  supersedes?: string | null;
  qa?: Qa;
  /** Denormalised labels, when the API provides them. */
  subject_label?: string;
  object_label?: string;
}

export interface ObjectDetail extends TraceObject {
  links_out?: LinkRef[];
  links_in?: LinkRef[];
  claims?: Claim[];
  tags?: Tag[];
}

export interface Lens {
  name: string;
  description?: string;
  paths?: string[][];
  types?: string[];
  predicates?: string[];
  excludes?: string[][];
}

export interface Health {
  status?: string;
  env?: string;
  version?: string;
  objects?: number;
  links?: number;
  claims?: number;
  taxonomy?: { url?: string; reachable?: boolean; version?: string };
}

export interface Stats {
  objects_by_type?: Record<string, number>;
  links_by_predicate?: Record<string, number>;
  qa_bands?: Record<string, number>;
  by_source?: Record<string, number>;
  last_ingest?: Record<string, string>;
  totals?: { objects?: number; links?: number; claims?: number };
}

export interface ObjectList {
  total: number;
  items: TraceObject[];
}

export interface PathHop {
  from: string;
  predicate: string;
  to: string;
}

export interface PathResult {
  nodes: GraphNode[];
  edges: GraphEdge[];
  hops?: PathHop[];
  explanation?: string;
  length?: number;
}

export interface PathResponse {
  lens?: string;
  paths: PathResult[];
  explanation?: string;
}

export interface CoverageConcept {
  id: string;
  label: string;
  layer?: number | string;
  count: number;
  by_type?: Record<string, number>;
  uri?: string;
}

export interface CoverageResponse {
  layer?: number | string;
  concepts: CoverageConcept[];
  unmatched_terms?: { term: string; count: number; example?: string }[];
  totals?: { tagged_objects?: number; objects?: number };
}

export interface ClaimList {
  total: number;
  items: Claim[];
}

export interface AskResponse {
  answer: string;
  tool_calls?: { name: string; args?: Attrs }[];
  objects_cited?: { id: string; label?: string; type?: string }[];
}

export interface ApiError extends Error {
  status: number;
  detail?: string;
}

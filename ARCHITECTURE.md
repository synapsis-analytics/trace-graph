# ARCHITECTURE

TRACE Graph is one FastAPI process per environment. It owns a SQLite database, serves a React SPA, exposes an HTTP
API and an MCP server, and calls exactly one external service (the MELIAF taxonomy service) — optionally, degrading
to a vendored copy when it is down.

```
                    ┌──────────────────────────────── one process, one SQLite file ───────────────────────────────┐
 browser  ──HTTP──► │  app/main.py   ── / ─────────►  frontend/dist (React + sigma.js SPA)                        │
                    │                ── /api/* ────►  app/api/{objects,graph,claims,ops}.py                       │
 agent    ──MCP───► │                ── /mcp/ ─────►  app/mcp_server.py (11 tools, 2 resource templates)          │
                    │                ── /docs ─────►  OpenAPI                                                     │
                    │                                                                                             │
 CLI      ─────────►│  app/cli.py: load · rebuild · qa-rerun · publish · export · stats · serve                   │
 ingest   ─────────►│  ingest/{prms,cgspace,porb,toc,taxonomy}.py ──► data/claims/*.jsonl ──┐                     │
                    │                                                                        ▼                    │
                    │  app/registry.py  append_claim → app/qa.py (8 checks, qa/rules.yaml) → materialise          │
                    │        │                                                                                    │
                    │        ├── claims  (append-only, `seq` = replay order, supersede chains)                    │
                    │        ├── objects (+ alt_ids, + objects_fts FTS5) ──┐                                      │
                    │        └── links   (subject, predicate, object)  ────┴─► app/graph.py, app/objects.py       │
                    │                                                                                             │
                    │  app/taxonomy_client.py ──HTTP──► MELIAF taxonomy service :8420 (resolve / export / term)   │
                    │  app/ask.py             ──HTTP──► OpenAI (optional; the ONLY LLM call in the system)        │
                    └─────────────────────────────────────────────────────────────────────────────────────────────┘
```

## The six TRACE pieces → modules

| Jules' piece | Module | Notes |
|---|---|---|
| 1. Identifier service | `app/ids.py` | `trace:<type>:<slug>`; slugs derive from the **source primary key**, never from titles. `alt_ids` (12 schemes) are normalised (handle/DOI prefixes stripped, ISO upper-cased) and resolvable at `GET /api/resolve-id`. |
| 2. Taxonomy service | `app/taxonomy_client.py`, `ingest/taxonomy.py` | Not reimplemented: the existing MELIAF service is called over HTTP. A frozen export is vendored (`data/seed/taxonomy_v0.2.0.json`) so tests and offline runs still resolve. |
| 3. Identity / signing | `app/signing.py`, `attested_by` + `provenance` on every claim | HMAC-SHA256 over a canonical claim with a per-agent secret; deliberately labelled a stand-in for did:web/VC. Writes need `X-Access-Key`. |
| 4. Claims registry | `app/registry.py` | Append-only. `assert_object`, `assert_link`, `assert_attr`, `retract`, `candidate_concept`. Corrections use `supersedes`. `rebuild()` replays the log; it is idempotent **including the edge ids** (deterministic `lnk_h…` hashes). |
| 5. QA / reconciliation | `app/qa.py`, `qa/rules.yaml` | `well_formed`, `id_resolvable`, `duplicate`, `taxonomy_resolvable`, `plausible_geo`, `plausible_time`, `evidence_present`, `provenance_strength`. Score starts at 1.0, each failure subtracts its weight (soft failures ×0.7). Bands: ≥0.85 accepted · 0.6–0.85 review · <0.6 rejected (stored and visible, never deleted). |
| 6. Lineage graph | `app/graph.py`, `app/lenses.py`, `lenses.yaml` | Neighbourhood BFS (depth 1–3), shortest explainable path, whole-graph export with degree sizing and community detection, coverage map. Lenses filter on the **(subject type, predicate, object type)** triple. |

## Request flow (example: opening a result in the UI)

1. `GET /api/graph?lens=delivery&limit=2000` → `app/api/graph.py` → `app.graph.whole_graph()`: densest-first node
   selection, lens-filtered edges, `size = 1 + log(degree)`, `attrs.community` from greedy modularity.
2. The user clicks a node → `GET /api/objects/{id}` → `app/objects.py`: the object row, `links_out` / `links_in`
   (each with a denormalised `neighbour {id, type, label}`), `tags[]` (from `TAGGED_WITH`), and `claims[]` — the full
   history in registry order, with attestor, provenance, evidence and supersede links.
3. "Trace path to…" → `GET /api/path?from=…&to=…&lens=…` → BFS over lens-allowed edges, traversed in both directions
   but reported with direction, plus a plain-English `explanation`. No valid path is a **200 answer with an
   explanation**, not an error; only an unknown id is a 404.
4. Any write (`POST /api/claims`) goes through `append_claim` → QA → materialise. `?dry_run=1` returns the QA verdict
   without writing — the UI shows it before the user commits.

## Storage

One SQLite file (WAL, `busy_timeout`), **one connection per call** — never shared across threads. Tables:

| Table | Role |
|---|---|
| `claims` | the registry: id, kind, subject/predicate/object, payload, attestor, provenance, evidence, source, `supersedes`, qa json, status, `seq` |
| `objects` | materialised objects (+ `attrs_json`, `alt_ids_json`, `source_json`, `qa_json`) |
| `objects_fts` | FTS5 index over label + description (search) |
| `alt_ids` | (scheme, value) → object, unique — the resolver and the duplicate check |
| `links` | (subject, predicate, object) unique, indexed both ways, deterministic ids |
| `versions` | published snapshots |
| `ingest_runs` | last run per channel (shown in `/api/stats`) |
| `agents` | signing secrets for `provenance: signed` |

Objects and links are **derived data**: deleting `data/trace.db` and running `load` + `rebuild` reproduces them
exactly. The durable artefacts are `data/claims/*.jsonl` (committed) and `data/versions/*` (committed).

## Frontend

Vite + React 18 + TypeScript strict + Tailwind; graph rendering with **sigma.js v3 + graphology** (WebGL,
ForceAtlas2 in a worker, Louvain colouring). TanStack Query for fetching, react-router for routes. Seven pages:
Explore, Path finder, Framework, Coverage, Registry, Ask, API & MCP guide. Built to `frontend/dist` and served by
FastAPI with an index fallback, so there is a single origin and no CORS problem in production. The SPA also enforces
lens rules client-side, so what it draws matches what it says.

## MCP

`app/mcp_server.py` exposes the same semantics as the API: `trace_search`, `trace_get`, `trace_neighbourhood`,
`trace_path`, `trace_resolve_id`, `trace_coverage`, `trace_lenses`, `trace_claims`, `trace_append_claim` (key),
`trace_tag_text`, `trace_stats`, plus resources `trace://object/{id}` and `trace://lens/{name}`. Mounted at `/mcp/`
(streamable HTTP, stateless — it sits behind the tunnel) and runnable over stdio (`trace-mcp`) for desktop clients.
Built on the `mcp` Python SDK ≥ 2.0 (`MCPServer`, with a `FastMCP` fallback for 1.x).

## What is deliberately **not** here

* No accounts, no OAuth, no PKI — one shared access key per environment and an HMAC signature stand-in.
* No cloud: three launchd services on a Mac mini behind the existing tunnel. The AWS path is documented in
  `docs/ENVIRONMENTS.md`, not built.
* No LLM anywhere in the data path. Ingestion, QA, tagging, paths, coverage and aggregation are deterministic and
  reproducible; `/api/ask` is the single, optional exception.

# Changelog

All notable changes to TRACE Graph. The format follows [Keep a Changelog](https://keepachangelog.com/);
graph snapshots are versioned separately in `data/versions/`.

## [v0.1.0] — 2026-09-15

First public prototype: the whole loop end to end, on one real slice of the portfolio.

### Added
* **Claims registry** (`app/registry.py`) — append-only, `assert_object` / `assert_link` / `assert_attr` / `retract`
  / `candidate_concept`, supersede chains, deterministic replay (`rebuild`) that is idempotent down to the edge ids.
* **QA / reconciliation engine** (`app/qa.py`, `qa/rules.yaml`) — eight deterministic checks, editable weights,
  per-type fuzzy-duplicate thresholds, bands `high → accepted` / `medium → review` / `low → rejected`.
* **Lineage graph** (`app/graph.py`) — neighbourhood (depth 1–3), explainable shortest paths, whole-graph export with
  degree sizing and community detection, taxonomy coverage map.
* **Lenses** (`lenses.yaml`) — `portfolio`, `delivery`, `evidence`, `money`, `partnership`; the money lens refuses
  `result → country`; budgets are attributes with boundaries, never edges.
* **Five intake channels** (`ingest/`) — PRMS, CGSpace, PORB, ToC/results-framework, MELIAF taxonomy; re-runnable,
  byte-stable, callable from the CLI or `POST /api/ingest/{channel}`.
* **HTTP API** (`docs/API.md`) — 20 endpoints, reads open, writes behind `X-Access-Key`, OpenAPI at `/docs`.
* **MCP server** (`docs/MCP.md`) — 11 tools + 2 resource templates over streamable HTTP (`/mcp/`) and stdio.
* **SPA** (`frontend/`) — Explore (sigma.js WebGL), Path finder, Framework tree, Coverage, Registry/review,
  Ask, API & MCP guide; served by FastAPI from `frontend/dist`.
* **Identity** (`app/signing.py`) — `attested_by` + `provenance` (`signed` / `recorded` / `harvested`), HMAC-SHA256
  signatures as a labelled stand-in for did:web/VC.
* **Versions** — `publish` / `export` to JSON, GraphML and CSV; `data/versions/v0.1.0.*` committed.
* **Three environments** — dev `develop` :8413, test `staging` :8414, prod `main` :8415, launchd + `scripts/deploy.sh`.
* **Tests** — 169 pytest, 23 vitest, 19 end-to-end Playwright checks (`tests/e2e/smoke.mjs`); GitHub Actions CI.
* **Docs** — `README.md`, `PROCESS.md`, `ARCHITECTURE.md`, `docs/{API,MCP,DATA-MODEL,LENSES,ENVIRONMENTS,UI-GUIDE,DEMO-SCRIPT}.md`,
  `data/seed/SEED-REPORT.md`.

### Seed slice (SP01 "Breeding for Tomorrow")
7,883 claims → **1,310 objects · 6,247 links**; 7,802 accepted, 81 in review, 0 rejected;
2,865 `TAGGED_WITH` links against taxonomy v0.2.0, 40 candidate concepts, 12 PRMS↔CGSpace `SAME_AS` bridges.

### Known limitations
* `result → HLO` and `HLO → outcome` are documented heuristics (banded `medium`) until a ToC Explorer export exists.
* 259 accepted link claims point at objects still in review, so those edges are not drawn.
* `/api/ask` needs an `OPENAI_API_KEY`; without one it answers 503 with a notice. The model name is unverified.
* The public URLs sit behind the shared nginx basic auth of the `synaptic` gateway.

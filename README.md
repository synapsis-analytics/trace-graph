# TRACE Graph

**Taxonomy-Referenced Attestation & Continuous Evidence** — a small, open, versioned **claims registry +
lineage graph** over CGIAR portfolio knowledge: PRMS results, CGSpace knowledge products, PORB plans and
budgets, the results framework, and the MELIAF taxonomy.

![Explore](docs/img/explore.png)

## What it is

Every thing — programme, area of work, high-level output, KPI, outcome, result, knowledge product, innovation,
partner, country, project, MELIA study, taxonomy concept, author, document — is a **persistent data object** with a
TRACE id (`trace:result:prms-28526`) and alternate identifiers (PRMS id, CGSpace handle, DOI, CLARISA id, ISO-2,
taxonomy term id…).

Every fact about an object — **including every link** — enters as an **append-only claim** that says *what, about
which object(s), by whom, when, on what evidence, in which taxonomy terms*. Nothing is ever updated or deleted: a
correction is a new claim that `supersedes` the old one, a withdrawal is a `retract` claim. Each claim passes a
deterministic **QA gate** (eight checks, editable weights in `qa/rules.yaml`) that scores it and bands it
`high → accepted` / `medium → review` / `low → rejected` — rejected claims are still stored and visible.

The accepted claims **materialise** into a graph that people explore visually and that agents query through an
**HTTP API** and an **MCP server**. Rebuilding the graph from the claim log is idempotent down to the ids
(`trace-api rebuild`), so the graph is always a pure function of the registry.

This implements the six pieces of Jules Colomer's TRACE concept: identifier service (`app/ids.py`), taxonomy
service (the separate MELIAF service, called over HTTP), identity/signing layer (`app/signing.py`, HMAC stand-in for
did:web/VC), claims registry (`app/registry.py`), QA/reconciliation engine (`app/qa.py`), lineage graph
(`app/graph.py`). See `ARCHITECTURE.md`.

## Why the design looks like this

* **Typed links + lenses.** "Kenya as a portfolio concept" and "Kenya attached to one result" are the same node, but a
  path through it is only valid for some questions. A **lens** (`lenses.yaml`, `GET /api/lenses`) is a named, explainable
  set of allowed path patterns: `portfolio`, `delivery`, `evidence`, `money`, `partnership`. The `money` lens
  deliberately refuses `result → country`, because budgets must not be prorated across neighbours.
* **Attribute boundaries.** A budget lives *on* the PORB HLO object; there is no `BUDGETED` edge and nothing
  propagates it. The UI says so in the drawer.
* **Count distinct by id.** Aggregations count objects by TRACE id, never by row, so partners reported by several
  centres are not double-counted.
* **Everything works without an LLM.** Ingestion, QA, tagging, paths and coverage are deterministic. The only
  optional model call is `/api/ask` (503 with a friendly notice when there is no key).

## Quick start

```bash
git clone https://github.com/synapsis-analytics/trace-graph.git && cd trace-graph
python3.12 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env                     # set TRACE_ACCESS_KEY
./.venv/bin/python -m app.cli load data/claims/seed-*.jsonl     # ~75 s, 7,883 claims
(cd frontend && npm ci && npm run build)
./scripts/run.sh                         # http://127.0.0.1:8413
```

The seed slice (committed, public) is **Science Program SP01 "Breeding for Tomorrow"**:
**1,310 objects · 6,247 links · 7,883 claims · 81 items in the review queue**, tagged against MELIAF taxonomy v0.2.0.

## Environments

| Env | Branch | Port | URL |
|---|---|---|---|
| dev | `develop` | 8413 | https://p8413.synaptic.synapsis-analytics.com |
| test | `staging` | 8414 | https://p8414.synaptic.synapsis-analytics.com |
| prod | `main` | 8415 | https://p8415.synaptic.synapsis-analytics.com |

All three run under launchd on the Mac mini; `scripts/deploy.sh <dev|test|prod>` is the whole deployment.
See `docs/ENVIRONMENTS.md` (including the documented AWS path) and `PROCESS.md` for the promotion flow.

## API and MCP

* HTTP: `GET /health`, `/api/stats`, `/api/objects`, `/api/objects/{id}`, `/api/objects/{id}/neighbourhood`,
  `/api/path`, `/api/graph`, `/api/lenses`, `/api/resolve-id`, `/api/coverage`, `/api/claims`,
  `POST /api/claims` (`?dry_run=1`), `/api/claims/{id}/decide`, `/api/ingest/{channel}`, `/api/tag`, `/api/ask`,
  `/api/versions`, `/api/export/{version}.json|csv|graphml`. Reads are open, writes need `X-Access-Key`.
  Full reference: `docs/API.md` · OpenAPI at `/docs`.
* MCP (streamable HTTP at `/mcp/`, or stdio via `trace-mcp`): `trace_search`, `trace_get`, `trace_neighbourhood`,
  `trace_path`, `trace_resolve_id`, `trace_coverage`, `trace_lenses`, `trace_claims`, `trace_append_claim`,
  `trace_tag_text`, `trace_stats` + resources `trace://object/{id}`, `trace://lens/{name}`. See `docs/MCP.md`.

```bash
claude mcp add --transport http trace-graph https://p8415.synaptic.synapsis-analytics.com/mcp/
```

## Repository map

| Path | What |
|---|---|
| `app/` | FastAPI backend: registry, QA, graph, lenses, taxonomy client, versions, MCP, SPA serving |
| `ingest/` | the five intake channels (`prms`, `cgspace`, `porb`, `toc`, `taxonomy`) + claim builders |
| `frontend/` | React + Vite + sigma.js explorer (built to `frontend/dist`, served by FastAPI) |
| `data/seed/` | vendored public input extracts + `SEED-REPORT.md` |
| `data/claims/` | the committed seed claim batches (jsonl) — the durable artefact |
| `data/versions/` | published snapshots (`v0.1.0.json` + `.graphml` + `.csv`) |
| `qa/rules.yaml`, `lenses.yaml` | the editable rules of the game |
| `scripts/` | `deploy.sh`, `launchd-install.sh`, `launchd-uninstall.sh`, `run.sh` |
| `tests/` | 169 pytest tests + 23 vitest tests + `tests/e2e/smoke.mjs` (19 end-to-end checks) |
| `docs/` | `API.md`, `MCP.md`, `DATA-MODEL.md`, `LENSES.md`, `ENVIRONMENTS.md`, `UI-GUIDE.md`, `DEMO-SCRIPT.md` |

## Status and licence

Prototype, built 2026-09-15. Everything in it is **public data**; the numbers are *assumptions to react to, not
decisions*. Two mappings are explicitly heuristic (result→HLO, HLO→outcome) and are banded `medium` in the graph —
see `data/seed/SEED-REPORT.md`. MIT licence (`LICENSE`).

# TRACE Graph — HTTP API

Base URL: `http://127.0.0.1:${PORT}` (dev `:8413`, test `:8414`, prod `:8415`;
public `https://p8413|p8414|p8415.synaptic.synapsis-analytics.com`).
All data is public: **reads need no authentication**, CORS is open (`*`).
**Writes require the header `X-Access-Key: <TRACE_ACCESS_KEY>`** (401 otherwise). If
`TRACE_ACCESS_KEY` is empty the write endpoints are open — never do that outside a laptop.

Interactive OpenAPI: `GET /docs` · machine-readable: `GET /openapi.json`.

| Method | Path | Key | Purpose |
|---|---|---|---|
| GET | `/health` | – | liveness + counts + taxonomy reachability |
| GET | `/api/stats` | – | counts by type / predicate / band / status / source, last ingest per channel |
| GET | `/api/objects` | – | list & full-text search |
| GET | `/api/objects/{id}` | – | one object + links + claims + tags |
| GET | `/api/objects/{id}/neighbourhood` | – | graph around an object |
| GET | `/api/path` | – | shortest explainable path under a lens |
| GET | `/api/graph` | – | whole (filtered) graph for the explorer |
| GET | `/api/lenses` | – | lens definitions |
| GET | `/api/resolve-id` | – | alternate identifier → object |
| GET | `/api/coverage` | – | taxonomy coverage map + unmatched terms |
| GET | `/api/claims` | – | registry listing / review queue |
| GET | `/api/claims/{id}` | – | claim + QA detail + supersede chain |
| POST | `/api/claims` | ✅ | append a claim (`?dry_run=1` = QA only) |
| POST | `/api/claims/{id}/decide` | ✅ | human review decision |
| POST | `/api/ingest/{channel}` | ✅ | run an intake channel (`prms`,`cgspace`,`porb`,`toc`,`taxonomy`) |
| POST | `/api/tag` | ✅ | taxonomy resolve (+ write `TAGGED_WITH` claims) |
| POST | `/api/ask` | – | LLM Q&A over the graph (503 without `OPENAI_API_KEY`) |
| GET | `/api/versions` · POST `/api/versions/publish` | ✅ on publish | snapshots |
| GET | `/api/export/{version}.json\|csv\|graphml` | – | published snapshot download |
| – | `/mcp` | – | MCP streamable HTTP (see `docs/MCP.md`) |

---

## GET /health
```bash
curl -s localhost:8413/health
```
```json
{"status":"ok","env":"dev","version":"0.1.0","objects":312,"links":889,"claims":1204,
 "taxonomy":{"url":"http://localhost:8420","reachable":true,"version":"v0.2.0","offline_copy":true},
 "public_url":"https://p8413.synaptic.synapsis-analytics.com","db":"…/data/trace.db","frontend_built":true}
```
`taxonomy.reachable=false` is **not** an error: the backend degrades to the vendored export
(`data/seed/taxonomy_v0.2.0.json`).

## GET /api/stats
`{"totals":{"objects","links","claims","review_queue"}, "objects_by_type":{…},
"links_by_predicate":{…}, "claims_by_band":{…}, "claims_by_status":{…},
"claims_by_provenance":{…}, "objects_by_source":{…}, "last_ingest":{"prms":{"ran_at","counts"}},
"recent_versions":[…]}`

## GET /api/objects
Query: `type` (comma-separated), `q` (FTS5 prefix search over label+description), `limit` (≤500),
`offset`, `band` (`high|medium|low`), `source` (`prms|cgspace|porb|toc|taxonomy|fixture`).
```bash
curl -s "localhost:8413/api/objects?type=result&q=groundnut&limit=5"
```
```json
{"total":3,"items":[{"id":"trace:result:prms-24338","type":"result","label":"…","description":"…",
 "attrs":{"result_type":"Knowledge product","year":2025},
 "alt_ids":[{"scheme":"prms_result_id","value":"24338"}],
 "source":{"system":"prms","ref":"result.id=24338","snapshot":"prdb_20260913"},
 "qa":{"band":"high","score":0.95},"created_at":"…","updated_at":"…"}]}
```

## GET /api/objects/{id}
Adds `links_out`, `links_in` (each with the neighbour's `label`/`type`), `tags` (the
`TAGGED_WITH` subset), `claims` (full history for that object) and `claim_count`.
404 when the id is unknown.

## GET /api/objects/{id}/neighbourhood
Query: `depth` 1–3 (default 1), `lens`, `predicates` (comma list), `types` (comma list),
`limit` (node cap, default 300).
```bash
curl -s "localhost:8413/api/objects/trace:result:prms-24338/neighbourhood?depth=2&lens=delivery"
```
```json
{"root":"trace:result:prms-24338","found":true,"depth":2,"lens":"delivery",
 "nodes":[{"id":"…","type":"hlo","label":"Target markets","size":2.39,"band":"high",
           "attrs":{"budget_usd":68600,"degree":11}}],
 "edges":[{"id":"lnk_01J…","source":"…","target":"…","predicate":"CONTRIBUTES_TO","attrs":{},"band":"high"}],
 "truncated":false,"counts":{"nodes":12,"edges":12}}
```
`truncated=true` means the node cap was hit — raise `limit` or narrow the lens.

## GET /api/path
```bash
curl -s "localhost:8413/api/path?from=trace:result:prms-24338&to=trace:program:sp01&lens=delivery"
```
```json
{"found":true,"from":"…","to":"…","lens":"delivery",
 "paths":[{"length":1,"steps":[{"from":{"id","type","label"},"predicate":"REPORTED_UNDER",
            "direction":"out","to":{…},"attrs":{}}],"nodes":[…],"edges":[…],
           "explanation":"Result \"…\" is reported under Program \"Breeding for Tomorrow\"."}],
 "explanation":"…"}
```
Edges are traversed in both directions but always **reported with their direction** (`out` = the
predicate as stored, `in` = the inverse phrasing). `found:false` with a `reason` when no path
exists under that lens within `max_len` (default 6, max 8) — that is a meaningful answer, not an
error (e.g. `money` never reaches a country from a result).

## GET /api/graph
Query: `lens`, `types`, `predicates`, `limit` (≤5000, default 2000), `communities` (default true).
Returns the CONTRACT node/edge shape plus `attrs.community` (greedy-modularity clusters) and
`counts.total_objects`; nodes are chosen by degree, so `truncated=true` keeps the densest core.

## GET /api/lenses
`{"lenses":[{"name","label","description","paths","predicates","types","excludes","boundary_attrs","notes"}]}`

## GET /api/resolve-id
```bash
curl -s "localhost:8413/api/resolve-id?scheme=cgspace_handle&value=10568/175922"
```
Schemes: `prms_result_id`, `prms_result_code`, `cgspace_handle`, `doi`, `clarisa_institution_id`,
`iso2`, `clarisa_initiative_code`, `porb_row`, `taxonomy_term_id`, `taxonomy_uri`, `toc_result_id`.
Handles/DOIs are normalised (URL prefixes stripped, case-insensitive). 404 when unknown.

## GET /api/coverage
Query: `layer` (`1|2|3`), `group`, `limit`.
```json
{"layer":"2","concepts":[{"id":"trace:concept:l2-0074","label":"market intelligence","layer":"2",
   "by_type":{"result":11,"kp":7},"objects":18}],
 "concept_count":142,"unmatched_terms":[{"term":"maize seed systems","count":7,"layer":"1",
   "suggested_for":"L2","status":"review"}],
 "untagged_by_type":{"result":4},"coverage_pct":93.2,"taggable_objects":118,"tagged_objects":110}
```

## GET /api/claims · GET /api/claims/{id}
Query: `status` (`accepted|review|rejected|superseded`), `band`, `subject`, `kind`, `limit`, `offset`.
The **review queue** is `?status=review`. The detail view adds `supersede_chain` and `superseded_by`.

## POST /api/claims  (key)
Body = the claim CONTRACT (`docs/DATA-MODEL.md` §Claims). `?dry_run=1` runs validation + QA and
returns the scored claim **without storing anything** (`materialised:false`).
```bash
curl -s -X POST "localhost:8413/api/claims?dry_run=1" -H 'X-Access-Key: …' -H 'content-type: application/json' \
  -d '{"kind":"assert_link","subject":"trace:result:prms-24338","predicate":"WITH_PARTNER",
       "object":"trace:institution:clarisa-1234","attested_by":"person:j.berenguer","provenance":"recorded"}'
```
Response = the stored claim with `qa:{band,score,checks[],status}`, `status`, `materialised`.
`422` on schema violations, `401` without the key. Claims are **never** updated or deleted: send a
new claim with `supersedes` (or `kind:"retract"`) to correct one. Re-posting a claim with an
`id` that already exists is a no-op (`already_present:true`) so batch replays stay idempotent.

## POST /api/claims/{id}/decide  (key)
`{"decision":"accept|reject","by":"person:…","note":"…"}` → the decision is recorded on the claim
(`decided_by`, `decided_at`, a `human_review` check) and the graph is re-materialised.

## POST /api/ingest/{channel}  (key)
`{"limit":50}` → runs `ingest.<channel>` (entry point `run_channel`/`ingest`/`run`/`main`, called
with `limit=`). When the channel module is absent or has an incompatible signature, the committed
batches `data/claims/*<channel>*.jsonl` are replayed instead; `501` when there is neither.

## POST /api/tag  (key)
`{"text":"…"}` → `{matches:[{term_id,pref_label,matched_text,layer,via,uri,status}],source,reachable}` (read-only).
`{"object_ids":["trace:result:…"]}` → resolves each object's label+description, creates the
`concept` objects it needs and appends `TAGGED_WITH` claims; returns per-object tags and statuses.

## POST /api/ask
`{"question":"…"}` → `{"answer","model","tool_calls":[…],"objects_cited":["trace:…"]}`.
`503 {"detail":"OPENAI_API_KEY not configured"}` when no key; `502` when the provider fails.
The model may only call the deterministic MCP tools — it cannot query the DB directly.

## Versions & export
```bash
curl -s -X POST localhost:8413/api/versions/publish -H 'X-Access-Key: …' \
     -d '{"bump":"minor","notes":"seed v1"}' -H 'content-type: application/json'
curl -s localhost:8413/api/export/v0.1.0.graphml -o trace-v0.1.0.graphml
```
`publish` freezes the accepted graph to `data/versions/vX.Y.Z.json` and registers it; `export`
serves `json` (same shape as `/api/graph`), `csv` (one row per node/edge) or `graphml`
(Gephi/Cytoscape). 404 for an unpublished version, 400 for an unsupported format.

## Errors
`401` missing/invalid key · `404` unknown object/claim/version/channel · `400` bad arguments ·
`422` schema validation (FastAPI/pydantic) · `501` channel not implemented · `502` upstream LLM ·
`503` optional feature not configured. Bodies are always `{"detail": "…"}`.

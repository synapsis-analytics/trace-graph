# TRACE Graph — prototype plan & shared contract (2026-09-15)

> **Read this file in full before doing anything.** It is the single source of truth for every sub-agent working
> on the TRACE prototype. It fixes the vocabulary, the data model, the API contract, the file layout, the ports,
> and the rules. Sections marked **CONTRACT** must be implemented exactly as written so that the backend,
> frontend and data agents — who work in parallel and never see each other — fit together.

## 0. The ask (Jose, 15 Sep 2026, 19:40)

Jose asked the agent to **implement Jules Colomer's TRACE vision as a new, separate prototype**:

* new GitHub repo with **development / testing / production** environments so the concept can be *operationalised*;
* a **visual network-graph exploration tool** with "cool and modern" functionality **and** the same knowledge exposed
  through an **API + MCP server** so AI agents can navigate the relationships;
* a **starting data set**: ~50 PRMS results, ~50 CGSpace items (from the WEAI harvest), PORB data, the high-level
  results framework, and (optionally) taxonomy tagging through the existing MELIAF taxonomy service;
* a **process** for how this is maintained and sustained over time (ingestion → QA → publish), not a one-off;
* everything **public and open** — it is public data, no confidentiality concerns;
* a Word report (docx-illustrate) explaining what it is, how it works, how to use it, and how it answers the needs;
* **only Opus 5 sub-agents** (usage constraint), "move forward, don't get stuck, don't ask too many questions".

## 1. The vision we are implementing (sources in this folder)

* `SOURCE-TRACE-definition-jules-20260902.md` — Jules' full TRACE concept (**Taxonomy-Referenced Attestation &
  Continuous Evidence**, working name). One sentence: *"one identity, one vocabulary, one quality gate — applied
  everywhere evidence about an innovation lives, forwards and backwards in time, inside the walls and out."*
* `SOURCE-TRACE-six-pieces-jules-20260915.md` — the six components Jules posted today:
  1. **Identifier Service** — permanent ID per thing (dataset, innovation, Program…) that survives edits.
  2. **Taxonomy Service** — shared controlled vocabulary (SKOS) so claims are comparable.
  3. **Identity/Signing Layer** — records or verifies who makes a claim.
  4. **Claims/Records Registry** — append-only; a correction is a new entry that supersedes, never an overwrite.
  5. **QA/Reconciliation Engine** — scores each claim (duplicate? plausible? well-formed?) and bands it by confidence.
  6. **Lineage Graph** — query the whole chain in one go instead of reconstructing it by hand.
* `SOURCE-TRACE-teams-thread-20260902.md` — RAiD / SKOS / claims-registry discussion (Jules ↔ Jose).
* `SOURCE-transcript-jules-jose-20260915.txt` — today's call. Key points beyond the definition:
  * Jules: everything becomes a **data object with attributes, one of which is links to other objects**; *"on graph
    or off graph"* — free text that does not comply is off-graph; anyone (CG or non-CG) can **append** to an object,
    but only through the governance rule: **QA + taxonomy + registry (who/when)**. Examples of links we must show:
    dollars→results, evidence→innovation over time, field data→publication, innovation/publication/dataset→theory of
    change→technical report→PORB. *"CGIAR's knowledge base is itself a FAIR and persistent data object."*
  * Jules on the taxonomy slice: Layer 1 (AI graph, what is actually in the results) must be **reconciled against**
    Layer 2 (Lexicon) and Layer 3 (climate adaptation): show "how the text should have been worded", and route L1
    terms missing from L2/L3 as **candidate concepts**. Governance = distributed input → PPT screen → steering group.
  * Jose's concerns (design them in, do not hand-wave): (a) **granularity jumps** — "Kenya" as a portfolio-level
    concept vs "Kenya" attached to one result are the same node but a path through it is only valid for some
    questions → we need **typed links + "lenses"** (named, explainable path rules); (b) *"everything is connected to
    everything"* → relevance filtering / connectivity metrics / community clusters; (c) **money** cannot be
    prorated across neighbours → attributes have **boundaries** (a budget lives on the PORB HLO node and is
    *not* propagated); (d) **double counting** when summing over partners → unique IDs + explicit "count distinct
    by ID" in every aggregation; (e) a **semantic layer** of rules of the game; (f) *"let an agent loose on data we
    know by heart (results framework, PRMS) and see what it gets"* + *"ask without the graph"* (AI Q&A over it).
* `SOURCE-screenshot-prms-results-framework.png` — PRMS test env: **SP01 Breeding for Tomorrow → AOW01 Market
  Intelligence → HLO 1.AOW1.IO1 "Steer to impact" / HLO 2.AOW1.IO1 "Target markets" → KPIs/indicators** (centre-level
  activity lines such as "01-GATES W2 DLC … CIMMYT … Groundnut ESA"). That is the results-framework hierarchy the
  prototype must reproduce as objects: Program → Area of Work → High-Level Output → Indicator/KPI → Result.

### What "TRACE Graph" is, in one paragraph
A small, open, versioned **claims registry + lineage graph** over CGIAR's portfolio knowledge. Every thing (program,
area of work, output, outcome, result, knowledge product, innovation, partner, country, funder/project, MELIA study,
taxonomy concept) is a **persistent data object** with a TRACE ID and alternate identifiers. Every fact about an
object — including every link — enters as an **append-only claim** that says *what, about which object(s), by whom,
when, on what evidence, in which taxonomy terms*, and passes a **QA gate** that bands it by confidence. The
accepted claims materialise into a graph that people explore visually and agents query through an **API + MCP**.
Ingestion from PRMS, CGSpace, PORB, ToC and the taxonomy service are simply four **intake channels** writing claims
into the same registry — Jules' "one framework, three intake modes" (forward / backward / internal).

## 2. Decisions (taken by the orchestrator — assumptions are fine, we course-correct later)

| # | Decision | Why |
|---|---|---|
| D1 | **Separate repo** `synapsis-analytics/trace-graph` (public). Local path `~/workspace/trace-graph/`. | Jose: "most likely a separate thing". The taxonomy service stays what it is (one slice); TRACE **calls** it. |
| D2 | **Stack**: FastAPI + SQLite (Python 3.12, `.venv`) · React 18 + Vite + TypeScript SPA served by FastAPI from `frontend/dist` · graph rendering with **sigma.js v3 + graphology** (WebGL, handles thousands of nodes) · MCP via the official `mcp` Python SDK (FastMCP) mounted at `/mcp` (streamable HTTP) and runnable over stdio. | Same proven shape as the taxonomy prototype (built in one night, runs under launchd); no cloud dependency for the demo. |
| D3 | **Three environments on the Mac mini**, one git worktree per env, branch-per-env, launchd per env: **dev `develop` :8413 · test `staging` :8414 · prod `main` :8415** → public URLs `https://p8413|p8414|p8415.synaptic.synapsis-analytics.com` (tunnel forwards 8400–8420; 8410/8412/8419/8420 are taken). Promotion = merge develop→staging→main + `deploy.sh <env>`. GitHub Actions CI runs lint+tests on every push/PR. | Gives Jose real dev/test/prod today with zero AWS cost; the AWS path (Amplify + Lambda/EC2 via the CI/CD playbook) is documented as the next step, not built now. |
| D4 | **Data slice = Science Program SP01 "Breeding for Tomorrow"** (matches the screenshot) + the portfolio spine (all 13 SPs as program objects, so cross-program links are possible) — 50 PRMS results (Reporting 2025, QA'd), 50 CGSpace items tagged SP01, the SP01 PORB (HLOs, partners, W3/bilateral projects, MELIA studies, countries, outcomes, budgets), the SP01 results-framework hierarchy. | "Something we know by heart" (Jose). Small enough to read entirely, rich enough to show every link type. |
| D5 | **Taxonomy = the live MELIAF taxonomy service** `http://localhost:8420/api/resolve` (Layer 2 Lexicon + Layer 3 climate, deterministic, free) → `TAGGED_WITH` claims + a **coverage map**; terms found by the AI Layer 1 that have no L2/L3 match become **candidate concepts** in the review queue (Jules' reconciliation ask). A frozen copy of the taxonomy export is vendored for tests/offline. | Jose: "maybe there is an endpoint that checks validity and tags concepts". Reuses the existing prototype instead of duplicating it. |
| D6 | **Identity layer = honest, lightweight**: every claim has `attested_by` (agent id) + `provenance` ∈ {`signed`, `recorded`, `harvested`}; `signed` = HMAC-SHA256 over the canonical claim with a per-agent shared secret (a stand-in for did:web/VC that we label as such). No accounts, no OAuth in the prototype; write endpoints need `X-Access-Key`. | Jules' spec says internal/retrospective claims are "recorded", partner claims "signed"; we reproduce that distinction without building a PKI. |
| D7 | **LLM use is minimal and optional**: ingestion, QA and coverage are deterministic; the only LLM features are `/api/ask` (Q&A over the graph with tool use, OpenAI `gpt-5.5`, key from `.env`) and the taxonomy service's own `align`. Everything else must work with no key. | Usage constraint + reproducibility. |
| D8 | **Model tier for builders: Claude Opus 5, effort medium** (Jose's explicit constraint today; overrides the 09-12 "Fable only" rule for this job). | Usage budget. |

## 3. CONTRACT — data model

### 3.1 Identifiers
* TRACE ID: `trace:<type>:<slug-or-hash>` — lowercase, URL-safe. Type prefixes below. Slugs are derived from the
  **source primary key**, never from titles (titles change): e.g. `trace:result:prms-24338`,
  `trace:kp:hdl-10568-175922`, `trace:program:sp01`, `trace:aow:sp01-aow01`, `trace:hlo:sp01-hlo2-aow1-io1`,
  `trace:institution:clarisa-1234`, `trace:country:ke` (ISO-3166 alpha-2), `trace:concept:L2-0074`,
  `trace:project:porb-<sha1-12 of program|center|project title>`, `trace:melia:porb-<sha1-12>`.
* Every object carries `alt_ids: [{scheme, value}]` — schemes: `prms_result_id`, `prms_result_code`, `cgspace_handle`,
  `doi`, `clarisa_institution_id`, `iso2`, `clarisa_initiative_code`, `porb_row`, `taxonomy_term_id`, `taxonomy_uri`,
  `toc_result_id`. The resolver `GET /api/resolve-id?scheme=&value=` returns the TRACE object.

### 3.2 Object types (`type`)
`program` · `aow` (area of work) · `hlo` (high-level output / output-level indicator group) · `indicator` (KPI line
under an HLO, from PORB HLO sheet / PRMS) · `outcome` (ToC outcome: I-OC / 2030-OC / EoI outcome) · `result` (PRMS
result, any result type; keep `result_type` attr) · `kp` (knowledge product = CGSpace item; a PRMS "Knowledge product"
result that has a handle is a `result` object **SAME_AS-linked** to the `kp` object) · `innovation` (PRMS innovation
development/use detail) · `institution` (CLARISA partner/centre) · `country` · `region` · `project` (W3/bilateral
project from PORB) · `melia_study` (from PORB MELIA sheet) · `concept` (taxonomy term, layer 1/2/3) · `person` (only
authors from CGSpace, optional) · `document` (a big high-level document such as a PORB workbook or results framework
doc, when we want to point at it as a whole).

Common object fields — **CONTRACT**:
```json
{"id":"trace:result:prms-24338","type":"result","label":"…","description":"…",
 "attrs":{"result_type":"Knowledge product","year":2025,"status":"Quality Assessed","budget_usd":68600,"…":"…"},
 "alt_ids":[{"scheme":"prms_result_id","value":"24338"}],
 "source":{"system":"prms","ref":"result.id=24338","snapshot":"prdb_20260913"},
 "created_at":"…","updated_at":"…","claim_count":7,"qa":{"band":"high","score":0.93}}
```

### 3.3 Link types (`predicate`) — every link is directed `subject → object`
| predicate | from → to | meaning / source |
|---|---|---|
| `PART_OF` | aow→program, hlo→aow, indicator→hlo, outcome→program | results-framework hierarchy (PORB + PRMS) |
| `CONTRIBUTES_TO` | result→hlo / indicator / outcome | PRMS ToC/indicator mapping (`results_toc_result`, `contribution_to_indicators`); PORB outcome targets |
| `REPORTED_UNDER` | result→program | `results_by_inititiative` (role 1 = primary) |
| `PRODUCED_BY` | result→institution (CGIAR centre, lead) | PRMS `results_by_institution` where leading / centre type |
| `WITH_PARTNER` | result→institution | PRMS `results_by_institution` (non-lead) ; PORB Partners sheet: hlo→institution |
| `LOCATED_IN` | result / hlo / project / melia_study → country (or region) | PRMS `result_country` / `result_region`; PORB countries + location of benefit (`attrs.share_pct`) |
| `EVIDENCED_BY` | result→kp / result→document (URL) | PRMS `evidence` rows (link attr), `results_knowledge_product` |
| `SAME_AS` | result(kp-type)→kp | PRMS knowledge-product handle == CGSpace handle (**the PRMS↔CGSpace bridge**) |
| `DESCRIBES` | kp→innovation / result | CGSpace item cites a PRMS result or innovation (optional, when detectable) |
| `FUNDED_BY` | hlo / result → project | PORB W3-Bilateral sheet (project title → HLO), `attrs.amount_usd` |
| `BUDGETED` | hlo→program (self-attr) | do **not** create a link; the budget is an **attribute on the HLO** (boundary rule, D-Jose-c) |
| `STUDIED_BY` | outcome→melia_study | PORB MELIA sheet |
| `SYNERGY_WITH` | hlo→program (other program) | PORB Synergy Programs sheet |
| `TAGGED_WITH` | any→concept | taxonomy resolve; `attrs: {matched_text, via, layer, confidence}` |
| `BROADER` | concept→concept | taxonomy hierarchy |
| `CANDIDATE_FOR` | concept(layer1/free term)→concept(layer2/3) | reconciliation suggestion (review queue) |
| `SUPERSEDES` | claim→claim (registry-level, not graph) | corrections |
| `AUTHORED_BY` | kp→person | CGSpace authors (optional) |

Link fields — **CONTRACT**: `{"id":"lnk_<ulid>","subject":"trace:…","predicate":"WITH_PARTNER","object":"trace:…",
"attrs":{…},"claim_id":"clm_…","qa":{"band":"high"}}`.

### 3.4 Claims (the registry) — **CONTRACT**
```json
{"id":"clm_01J…","kind":"assert_object|assert_link|assert_attr|retract|candidate_concept",
 "subject":"trace:…","predicate":"WITH_PARTNER","object":"trace:…",
 "payload":{…object or link or attr body…},
 "attested_by":"ingest:prms@synapsis|agent:opus-5|person:j.berenguer|partner:demo-ngo",
 "provenance":"harvested|recorded|signed","signature":null,
 "evidence":[{"kind":"url|handle|doi|file|text","value":"…"}],
 "taxonomy_version":"v0.2.0","source":{"system":"prms","ref":"…","snapshot":"…"},
 "created_at":"…","supersedes":null,
 "qa":{"band":"high|medium|low","score":0.0,"checks":[{"name":"well_formed","ok":true,"note":""}],"status":"accepted|review|rejected","decided_by":null,"decided_at":null}}
```
Rules: claims are **never updated or deleted**; a correction is a new claim with `supersedes`; a retraction is
`kind: retract`. The graph = the materialised view of *accepted* claims (latest in each supersede chain). Rebuilding
the graph from the claims log must be idempotent (`trace rebuild`).

### 3.5 QA / reconciliation engine — checks (deterministic, no LLM)
`well_formed` (schema, known type/predicate, both ends resolvable) · `id_resolvable` (subject/object exist or are
created in the same batch) · `duplicate` (exact alt-id match → SAME_AS suggestion instead of a new object; fuzzy
title ≥ 0.92 token-set ratio → `review`) · `taxonomy_resolvable` (for TAGGED_WITH: term exists, not deprecated; if
deprecated → propose `replaced_by`) · `plausible_geo` (country ISO valid; result LOCATED_IN must be a country in the
program's PORB countries **or** flagged `review` with note) · `plausible_time` (year within 2022–2026) · `evidence_present`
(links of kind EVIDENCED_BY carry a URL/handle/DOI) · `provenance_strength` (signed > recorded > harvested).
Scoring: start 1.0, subtract per failed check (weights in `qa/rules.yaml`); bands: `high ≥ 0.85 → accepted`,
`0.6–0.85 → review`, `< 0.6 → rejected` (still stored, visible, labelled — *never silently deleted*).

### 3.6 Lenses (Jose's granularity concern) — **CONTRACT**
A lens is a named, explainable set of allowed path patterns used by neighbourhood/path queries and by the UI filter.
Defined in `lenses.yaml`, exposed at `GET /api/lenses`. Ship these five:
* `portfolio` — program → aow → hlo → indicator/outcome (structure only);
* `delivery` — result → hlo/outcome/program + result → institution + result → country (what was delivered where, by whom);
* `evidence` — result ↔ kp (SAME_AS, EVIDENCED_BY) → concept; innovation → result → kp;
* `money` — project → hlo (FUNDED_BY), hlo budget attrs, partner budgets; **explicitly does not traverse** result → country (no prorating);
* `partnership` — institution ↔ result ↔ program, institution ↔ hlo (PORB) ↔ country.
Every lens has a `description` and a list of `paths` like `["result","CONTRIBUTES_TO","hlo","PART_OF","aow","PART_OF","program"]`.
Aggregations always report `count_distinct` by ID and, when an entity is reached via >1 path, say so (`via_paths`).

## 4. CONTRACT — HTTP API (prefix `/api`, JSON; write endpoints need header `X-Access-Key`)
| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | `{status, env, version, objects, links, claims, taxonomy:{url, reachable, version}}` |
| GET | `/api/stats` | counts by type / predicate / qa band / source system; last ingest per channel |
| GET | `/api/objects?type=&q=&limit=&offset=&band=&source=` | list/search (FTS on label+description) → `{total, items}` |
| GET | `/api/objects/{id}` | object + `links_out`, `links_in` (with the neighbour's label/type), `claims[]` (history), `tags[]` |
| GET | `/api/objects/{id}/neighbourhood?depth=1..3&lens=&predicates=&types=&limit=` | `{nodes:[…], edges:[…], truncated:bool}` |
| GET | `/api/path?from=&to=&lens=&max_len=6` | shortest valid path(s) under the lens, with a plain-English explanation |
| GET | `/api/graph?lens=&types=&limit=` | whole (filtered) graph for the explorer: `{nodes, edges}` — sized ≤ 5k nodes |
| GET | `/api/lenses` | lens definitions |
| GET | `/api/resolve-id?scheme=&value=` | alt-id → object |
| GET | `/api/coverage?layer=2&group=` | taxonomy coverage map: per concept → #objects tagged, by type; plus `unmatched_terms` (candidates) |
| GET | `/api/claims?status=&band=&subject=&kind=&limit=` | registry listing (review queue = `status=review`) |
| GET | `/api/claims/{id}` | claim + QA detail + supersede chain |
| POST | `/api/claims` | **append a claim** (object/link/attr/candidate) → runs QA → returns claim with band/status; `?dry_run=1` returns QA only |
| POST | `/api/claims/{id}/decide` | `{decision: accept|reject, by, note}` (human review) |
| POST | `/api/ingest/{channel}` | `{limit?}` runs an intake channel (`prms`, `cgspace`, `porb`, `toc`, `taxonomy`) on the vendored seed inputs; returns the batch summary — used by `trace ingest` CLI too |
| POST | `/api/tag` | `{object_ids?:[…], text?:"…"}` → taxonomy resolve via the taxonomy service, returns matches; with object_ids it appends TAGGED_WITH claims |
| POST | `/api/ask` | `{question}` → `{answer, tool_calls:[…], objects_cited:[…]}` (optional; 503 with clear message when no key) |
| GET | `/api/versions` · POST `/api/versions/publish` | snapshot the accepted graph as `data/versions/vX.Y.Z.json` (+ release notes); `GET /api/export/{v}.json|csv|graphml` |
| GET | `/docs` | OpenAPI |
| — | `/mcp` | MCP streamable-HTTP endpoint (below) |

Node/edge JSON for graph views — **CONTRACT** (this is what the frontend renders):
`node = {id, type, label, size?:number, band?:"high|medium|low", attrs:{…}}`, `edge = {id, source, target, predicate, attrs:{…}}`.

### MCP tools (same semantics as the API; names are the contract)
`trace_search(query, type?, limit?)` · `trace_get(id)` · `trace_neighbourhood(id, depth?, lens?)` · `trace_path(from_id, to_id, lens?)`
· `trace_resolve_id(scheme, value)` · `trace_coverage(layer?)` · `trace_lenses()` · `trace_claims(status?, subject?)`
· `trace_append_claim(claim_json)` (needs key) · `trace_tag_text(text)` · `trace_stats()`. Resources: `trace://object/{id}`, `trace://lens/{name}`.

## 5. CONTRACT — repo layout (`~/workspace/trace-graph/`)
```
README.md  LICENSE(MIT)  PROCESS.md  ARCHITECTURE.md  CHANGELOG.md  .env.example  .gitignore
pyproject.toml  requirements.txt  requirements-dev.txt  pytest.ini
app/            FastAPI: main.py config.py db.py models.py ids.py registry.py qa.py graph.py lenses.py
                taxonomy_client.py ask.py mcp_server.py api/ (routers) static serving of frontend/dist
ingest/         channels: prms.py cgspace.py porb.py toc.py taxonomy.py + common.py (claim builders) ; cli.py (`trace ingest|rebuild|qa|publish|serve`)
qa/rules.yaml   lenses.yaml
data/seed/      vendored INPUT extracts (public): prms_sp01_results.json, cgspace_sp01_items.json, porb_sp01.json, toc_sp01.json, taxonomy_v0.2.0.json, SEED-REPORT.md
data/claims/    generated claim batches (jsonl) — committed for the seed so `rebuild` is reproducible
data/versions/  published snapshots (json)
data/trace.db   SQLite (git-ignored)
frontend/       Vite React TS app (src/…); build → frontend/dist (git-ignored; built by deploy.sh)
scripts/        deploy.sh <dev|test|prod> · launchd-install.sh · launchd-uninstall.sh · run.sh · seed.sh
tests/          pytest (backend, ingest, qa, mcp) · frontend vitest minimal
docs/           API.md MCP.md DATA-MODEL.md LENSES.md ENVIRONMENTS.md DEMO-SCRIPT.md
.github/workflows/ci.yml
```
Environment variables (`.env`): `TRACE_ENV=dev|test|prod`, `PORT`, `TRACE_DB_PATH`, `TRACE_ACCESS_KEY`,
`TAXONOMY_BASE_URL=http://localhost:8420`, `OPENAI_API_KEY` (optional), `TRACE_PUBLIC_URL`.

## 6. Starting data slice — what the DATA channel extracts (all public)
Sources on this Mac (read-only!):
* PRMS snapshot SQLite: `/Users/smithai/workspace/coding/PRMSDB/fresh_20260913/prdb_20260913.sqlite` (497 MB; open read-only
  `file:…?mode=ro`). Tables: `result` (version_id=6 "Reporting 2025", status_id=2 Quality Assessed), `result_type`,
  `results_by_inititiative` (inititiative_id=50 = SP01; `clarisa_initiatives` has SP01–SP13 ids 50–62),
  `results_by_institution` + `clarisa_institutions` (+`institution_role`, `clarisa_institution_types`),
  `result_country` + `clarisa_countries_regions`/`clarisa_regions` (country names: look for a `clarisa_countries` table),
  `results_knowledge_product` (handle, doi, findable/accessible/… FAIR flags), `evidence` (link, evidence_type_id),
  `results_innovations_dev`, `results_innovations_use_measures`, `results_toc_result` + `toc_result` (+`toc_level`),
  `results_toc_result_indicators`, `contribution_to_indicators`, `result_toc_impact_area_target`, `clarisa_impact_areas`.
  SP01 2025 QA'd counts: KP 421 · CapSha 115 · InnoDev 105 · Other output 55 · InnoUse 15 · Other outcome 11 · Policy 2.
  **Pick 50 results stratified**: ~12 KP (prefer those whose handle is in the CGSpace registry), ~10 InnoDev, ~8 CapSha,
  ~8 Other output, all 15 InnoUse? (cap 8), all 11 Other outcome (cap 6), both Policy changes — prefer results with
  partners + countries + evidence so the graph is dense. Note: `results_toc_result→toc_result` for 2025 may be empty
  (new portfolio ToC lives elsewhere) — try `results_toc_result_indicators`/`contribution_to_indicators`; if no
  structured link exists, map result→HLO through the PORB HLO sheet by centre + AoW (document the heuristic; band `medium`).
* CGSpace (WEAI harvest registry, read-only): `/Users/smithai/workspace/weai-local-corpus/data/registry.db` — tables
  `items(uuid, handle, name, dcterms_issued, text_extraction_status, text_path)`, `metadata_values(uuid, metadata_key,
  value)`; keys: `dc.title`, `dcterms.abstract`, `dc.identifier.uri`, `cg.identifier.doi`, `cg.contributor.programAccelerator`
  (= "Breeding for Tomorrow": 540 items), `cg.contributor.affiliation`, `cg.coverage.country`, `cg.coverage.iso3166-alpha2`,
  `cg.coverage.region`, `dcterms.subject`, `cg.subject.impactArea`, `cg.subject.sdg`, `dcterms.type`, `dc.contributor.author`,
  `cg.contributor.donor`, `cg.identifier.project`, `dcterms.license`, `dcterms.accessRights`, `cg.reviewStatus`.
  Raw JSON per item under `data/raw/<uuid>.json`, extracted text under `data/text/<uuid>.txt` (only ~1.7k items have text).
  **Pick 50 items**: first every SP01 item whose handle matches one of the 50 PRMS results' KP handles (SAME_AS bridge),
  then fill with SP01-tagged 2025/2026 items that have abstracts, preferring those with country + affiliation + subjects.
* PORB master (public, approved 2025 PORBs): `/Users/smithai/workspace/PORBs_consolidation/SummaryPORBs_v3/PORB_MASTER_All_Programs_13Aug2026.xlsx`
  sheets `HLO` (Program, AOW, Center, High Level Output, Description, KPI Type, Countries, Target, Budget, Assumption),
  `Partners`, `W3-Bilateral`, `MELIA`, `Cross Cutting`, `Outcomes` (Program, AOW, Outcome, Type, Indicator Type, Geo, Target),
  `Synergy Programs`, `Countries of Implementation` (%), `Location of Benefit` (%), `Anaplan`. Filter `Program/Accelerator ==
  "Breeding for Tomorrow"`; skip subtotal rows. Also create the 13 `program` objects from the distinct programs.
  CGSpace hosts the published PORB documents (e.g. handle 10568/175922 "Plan of Results and Budget 2025: CGIAR Science
  Program on …") — link each `program` to its PORB `kp` when found in the registry (`EVIDENCED_BY`).
* Results framework hierarchy: derive `aow`, `hlo`, `indicator`, `outcome` objects from the PORB sheets (codes like
  `HLO2.AOW1.IO1 Target markets`, `I-OC 3.5 …`, `2030-OC 2 …`); the screenshot confirms the same codes in PRMS.
* Taxonomy: `GET http://localhost:8420/api/export/current.json` (vendor as `data/seed/taxonomy_v0.2.0.json`),
  `POST /api/resolve {"text": …}` → matches `{term_id, pref_label, matched_text, layer, via, uri, status}`.
  Tag every result/kp/hlo/outcome label+description; store `TAGGED_WITH` claims (band by `via`: pref_label → high,
  alt_label/stem → medium). Terms are `concept` objects (create only the ones referenced + their `BROADER` chain).

## 7. The process (what makes it sustainable) — goes into `PROCESS.md`
1. **Intake channels are scripts, not one-offs**: `trace ingest prms|cgspace|porb|toc|taxonomy [--limit]` read a
   source, emit claims (jsonl) into `data/claims/<channel>-<date>.jsonl`, then `trace load` appends them to the
   registry and runs QA. Re-running is idempotent (same source key → same TRACE ID → duplicate check → no new object;
   changed attrs → `assert_attr` claim that supersedes).
2. **Every write goes through the same gate**: API `POST /api/claims` = MCP `trace_append_claim` = ingest scripts.
   QA bands; `review` items land in one queue (`/review` page); humans decide; decisions are claims too.
3. **Taxonomy loop**: unmatched frequent terms → `candidate_concept` claims → reviewed → (outside TRACE) proposed to the
   taxonomy service (`POST /api/terms` there) → next taxonomy version → re-tag. Governance per Jules: distributed input →
   PPT screen → Performance & Results Management steering group.
4. **Publish**: `trace publish --bump minor --notes "…"` freezes the accepted graph as a versioned snapshot (json +
   graphml + csv) — the FAIR "data object" that others can cite; diffs between versions available.
5. **Environments**: develop → dev (:8413) auto-deploys on push (deploy.sh pulls + restarts); staging → test (:8414) on
   merge; main → prod (:8415) on tagged release. CI (GitHub Actions) blocks merges on failing tests. AWS path documented.
6. **Refresh cadence**: PRMS snapshot is refreshed daily on this Mac (`prms-prdb-daily-delta-refresh`); CGSpace registry
   weekly (WEAI collector); PORB per approval cycle; taxonomy per published version. `trace ingest --since` picks deltas.

## 8. Work packages
| WP | Agent | Task file | Output |
|---|---|---|---|
| WP-D DATA | Opus 5 (medium) | `TASK-DATA.md` | `data/seed/*.json` + `data/claims/seed-*.jsonl` + `data/seed/SEED-REPORT.md` + `ingest/*.py` |
| WP-B BACKEND | Opus 5 (medium) | `TASK-BACKEND.md` | `app/*`, `qa/rules.yaml`, `lenses.yaml`, `tests/`, `docs/API.md`, `docs/MCP.md` |
| WP-F FRONTEND | Opus 5 (medium) | `TASK-FRONTEND.md` | `frontend/*` (built against the CONTRACT with a mock server until the backend exists) |
| WP-I INTEGRATION | Opus 5 (medium) | `TASK-INTEGRATION.md` (wave 2) | seed loaded, taxonomy tagged, QA run, 3 envs live, repo pushed, CI green, Playwright smoke |
| WP-R REPORT | orchestrator + Opus 5 | `TASK-REPORT.md` (wave 2) | `outputs/trace-proto-20260915/TRACE-Graph-Prototype-Report.docx` (illustrated) |

## 9. Rules for every sub-agent (non-negotiable)
* Work **only** inside `/Users/smithai/workspace/trace-graph/` (and your own scratch under `/tmp/trace-*`). Treat the
  source databases/spreadsheets as **read-only** (open SQLite with `?mode=ro`). Never modify the taxonomy service repo.
* Python: `python3.12 -m venv .venv` inside the repo (one venv, shared — check if it exists first; `pip install -r
  requirements.txt`). Node: `npm ci` inside `frontend/`. Do not install global packages.
* **Kill every test server you start** (`lsof -i :PORT -t | xargs kill`); never leave more than one uvicorn; use ports
  **8431–8439** for ad-hoc tests, never 8413/8414/8415/8420. Verify with `lsof` before finishing. Never run `find ~`.
* Never share one sqlite3 connection across threads: use per-request connections (`check_same_thread=False` + a lock,
  or a connection per request). WAL mode.
* Commit your work on branch `develop` with clear messages when your WP is done (`git add -A && git commit`); do
  **not** push and do not touch `main`/`staging` (the integration agent does).
* Write your final report to the path named in your task file, in markdown, with: what was built, how to run it, what
  was verified (commands + results), assumptions, open issues. The orchestrator only reads that file.
* If something is ambiguous, **decide, document the assumption, keep moving**. Do not stop to ask.

# TRACE Graph — data model

TRACE is an **append-only claims registry** whose accepted claims materialise into a **lineage
graph**. Nothing is ever overwritten: a correction is a new claim that supersedes the old one, and
a removal is a `retract` claim. `python -m app.cli rebuild` replays the whole log and must produce
exactly the same graph (idempotence is covered by tests).

```
intake channel ──► claim ──► QA gate ──► accepted? ──► materialised object / link
 (prms, cgspace,   (append)   (score,      │ no
  porb, toc,                   band)       └─► review queue (or rejected, still stored & visible)
  taxonomy, API, MCP)
```

## Identifiers
`trace:<type>:<slug>` — lowercase, URL-safe, derived from the **source primary key**, never from a
title. Examples: `trace:result:prms-24338` · `trace:kp:hdl-10568-175922` · `trace:program:sp01` ·
`trace:aow:sp01-aow01` · `trace:hlo:sp01-hlo2-aow1-io1` · `trace:institution:clarisa-1234` ·
`trace:country:ke` (ISO-3166 alpha-2) · `trace:concept:l2-0074` ·
`trace:project:porb-<sha1-12(program|center|title)>` · `trace:melia_study:porb-<sha1-12>`.

Every object also carries `alt_ids: [{scheme, value}]` (schemes: `prms_result_id`,
`prms_result_code`, `cgspace_handle`, `doi`, `clarisa_institution_id`, `iso2`,
`clarisa_initiative_code`, `porb_row`, `taxonomy_term_id`, `taxonomy_uri`, `toc_result_id`).
`GET /api/resolve-id?scheme=&value=` is the resolver; values are normalised (handle/DOI prefixes
stripped, ISO codes upper-cased) so `10568/175922` and `https://hdl.handle.net/10568/175922`
resolve to the same object. Helpers live in `app/ids.py`.

## Object types
`program` · `aow` · `hlo` · `indicator` · `outcome` · `result` · `kp` · `innovation` ·
`institution` · `country` · `region` · `project` · `melia_study` · `concept` · `person` · `document`.

```json
{"id":"trace:result:prms-24338","type":"result","label":"…","description":"…",
 "attrs":{"result_type":"Knowledge product","year":2025,"status":"Quality Assessed"},
 "alt_ids":[{"scheme":"prms_result_id","value":"24338"}],
 "source":{"system":"prms","ref":"result.id=24338","snapshot":"prdb_20260913"},
 "created_at":"…","updated_at":"…","claim_count":7,"qa":{"band":"high","score":0.93}}
```

## Link types
Every link is directed `subject → object` and carries the claim that created it.

| predicate | from → to |
|---|---|
| `PART_OF` | aow→program, hlo→aow, indicator→hlo, outcome→program |
| `CONTRIBUTES_TO` | result/innovation → hlo / indicator / outcome |
| `REPORTED_UNDER` | result→program |
| `PRODUCED_BY` | result/kp → institution (lead centre) |
| `WITH_PARTNER` | result/hlo/kp → institution |
| `LOCATED_IN` | result/hlo/project/melia_study/kp/aow → country or region |
| `EVIDENCED_BY` | result/program/innovation/hlo/outcome → kp or document |
| `SAME_AS` | any → any (the PRMS knowledge-product ↔ CGSpace item bridge) |
| `DESCRIBES` | kp/document → innovation or result |
| `FUNDED_BY` | hlo/result/program/aow → project |
| `STUDIED_BY` | outcome/hlo → melia_study |
| `SYNERGY_WITH` | hlo/program/aow → program |
| `TAGGED_WITH` | any → concept (`attrs: matched_text, via, layer, confidence`) |
| `BROADER` | concept → concept |
| `CANDIDATE_FOR` | concept (layer 1 / free term) → concept (layer 2/3) |
| `AUTHORED_BY` | kp/document → person |

`{"id":"lnk_<ulid>","subject":"trace:…","predicate":"WITH_PARTNER","object":"trace:…","attrs":{…},
"claim_id":"clm_…","qa":{"band":"high"}}`

**No `BUDGETED` link exists.** A budget is an attribute of the node that owns it (`hlo.attrs.budget_usd`,
`project.attrs.amount_usd`). Boundary attributes (`budget_usd`, `amount_usd`, `target`, `share_pct`)
are never propagated to neighbours and never prorated (PLAN D-Jose-c).

## Claims
```json
{"id":"clm_01J…","kind":"assert_object|assert_link|assert_attr|retract|candidate_concept",
 "subject":"trace:…","predicate":"WITH_PARTNER","object":"trace:…","payload":{…},
 "attested_by":"ingest:prms@synapsis|agent:opus-5|person:j.berenguer|partner:demo-ngo",
 "provenance":"harvested|recorded|signed","signature":null,
 "evidence":[{"kind":"url|handle|doi|file|text","value":"…"}],
 "taxonomy_version":"v0.2.0","source":{"system":"prms","ref":"…","snapshot":"…"},
 "created_at":"…","supersedes":null,
 "qa":{"band":"high","score":0.93,"checks":[{"name":"well_formed","ok":true,"note":""}],
       "status":"accepted","decided_by":null,"decided_at":null}}
```
* `assert_object` — `payload` is `{type,label,description,attrs,alt_ids,source}`; upserts and merges.
* `assert_attr` — `payload.attrs` merged into an existing object (used for corrections/updates).
* `assert_link` — `subject`+`predicate`+`object` (+`payload.attrs`); duplicate triples update in place.
* `retract` — removes a link (`subject`+`predicate`+`object`), the effect of a named claim
  (`payload.claim_id`/`supersedes`), or a whole object (subject only, with its links and alt-ids).
* `candidate_concept` — a Layer-1 term with no Lexicon match; never materialises, always lands in
  the review queue and feeds `unmatched_terms` in `/api/coverage`.

Statuses: `accepted` (materialised) · `review` (in the queue) · `rejected` (stored, visible,
labelled — never deleted) · `superseded` (a later accepted claim replaced it).

## Identity & signing (honest prototype)
`attested_by` names the agent/person/partner; `provenance` is `harvested` (scraped from a system of
record), `recorded` (a human or agent asserted it inside TRACE) or `signed` (HMAC-SHA256 over the
canonical claim with a per-agent shared secret from the `agents` table). This is an explicit
stand-in for did:web / Verifiable Credentials, not a PKI. QA scores `signed > recorded > harvested`.

## QA bands
Start at 1.0, subtract the weight of every failed check (`qa/rules.yaml`, editable):
`well_formed` · `id_resolvable` · `duplicate` · `taxonomy_resolvable` · `plausible_geo` ·
`plausible_time` · `evidence_present` · `provenance_strength`. Soft failures (fuzzy duplicate,
country outside the programme list) cost 70 % of their weight.
`≥0.85 → high/accepted` · `0.60–0.85 → medium/review` · `<0.60 → low/rejected`.

## Storage
SQLite (WAL, one connection per request, never shared across threads):
`objects` · `alt_ids(scheme,value)` unique · `links` (+ indexes both directions, unique on the
triple) · `claims` (+`seq` for replay order) · `objects_fts` (FTS5 over label+description) ·
`versions` · `agents` · `ingest_runs`. `data/trace.db` is git-ignored — the **claims batches** in
`data/claims/*.jsonl` are the durable artefact, and the database is always rebuildable from them.

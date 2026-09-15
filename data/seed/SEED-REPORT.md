# TRACE Graph — starting data slice (SEED REPORT)

**Generated:** 2026-09-15 · **Slice:** CGIAR Science Program **SP01 "Breeding for Tomorrow"** (2025) plus the
13-program portfolio spine · **Channels:** `prms`, `cgspace`, `porb`, `toc`, `taxonomy` · **All sources are public.**

Everything below is produced by re-runnable scripts in `ingest/` — nothing here was hand-made. Re-running the
pipeline against unchanged sources produces **byte-identical** files (verified: two consecutive runs, identical
MD5 for all 10 generated files), so `trace rebuild` from `data/claims/` is reproducible and git diffs are meaningful.

## 1. How to regenerate

```bash
cd ~/workspace/trace-graph && source .venv/bin/activate

# everything, in the right order (≈12 s end-to-end)
python -m ingest.cli all

# or one channel at a time (defaults shown)
python -m ingest.porb     --xlsx /Users/smithai/workspace/PORBs_consolidation/SummaryPORBs_v3/PORB_MASTER_All_Programs_13Aug2026.xlsx \
                          --program "Breeding for Tomorrow" --out data/claims/seed-porb.jsonl --extract data/seed/porb_sp01.json
python -m ingest.prms     --db /Users/smithai/workspace/coding/PRMSDB/fresh_20260913/prdb_20260913.sqlite \
                          --program SP01 --limit 50 --out data/claims/seed-prms.jsonl \
                          --extract data/seed/prms_sp01_results.json --porb-extract data/seed/porb_sp01.json
python -m ingest.cgspace  --registry /Users/smithai/workspace/weai-local-corpus/data/registry.db \
                          --program "Breeding for Tomorrow" --limit 50 --bridge data/seed/prms_sp01_results.json \
                          --out data/claims/seed-cgspace.jsonl --extract data/seed/cgspace_sp01_items.json
python -m ingest.toc      --porb-extract data/seed/porb_sp01.json --out data/claims/seed-toc.jsonl --extract data/seed/toc_sp01.json
python -m ingest.taxonomy --base http://localhost:8420 --claims 'data/claims/seed-*.jsonl' \
                          --out data/claims/seed-taxonomy.jsonl --vendor data/seed/taxonomy_v0.2.0.json
```

**Order matters:** `porb` → `prms` → `cgspace` → `toc` → `taxonomy`. PRMS needs the PORB HLO sheet for the
result→HLO heuristic; CGSpace bridges on the PRMS handles; ToC reads the PORB extract; taxonomy tags everything above.
(`ingest.cli all` runs `porb` twice — the second pass can match PORB partner names against the CLARISA institutions
that the PRMS extract has meanwhile vendored.)

`created_at` is frozen to the anchor `2026-09-15T20:00:00Z` (`--anchor`, or `TRACE_INGEST_NOW`); pass `--live-time`
for real-clock stamping in production runs.

## 2. What came out

| object type | prms | cgspace | porb | toc | taxonomy | object claims | **unique objects** |
|---|---:|---:|---:|---:|---:|---:|---:|
| `indicator` | · | · | 392 | · | · | 392 | **392** |
| `institution` | 174 | 80 | 67 | · | · | 321 | **247** |
| `person` | · | 134 | · | · | · | 134 | **134** |
| `concept` | · | · | · | · | 121 | 121 | **121** |
| `country` | 45 | 53 | 54 | · | · | 152 | **79** |
| `document` | 78 | · | · | 1 | · | 79 | **79** |
| `kp` | 31 | 33 | · | 13 | · | 77 | **77** |
| `project` | · | · | 74 | · | · | 74 | **74** |
| `result` | 50 | · | · | · | · | 50 | **50** |
| `candidate_concept` | · | · | · | · | 40 | 40 | **40** |
| `hlo` | · | · | 20 | · | · | 20 | **20** |
| `region` | 12 | · | 8 | · | · | 20 | **20** |
| `outcome` | · | · | 16 | · | · | 16 | **16** |
| `program` | 13 | · | 13 | · | · | 26 | **13** |
| `innovation` | 10 | · | · | · | · | 10 | **10** |
| `aow` | · | · | 5 | · | · | 5 | **5** |
| `melia_study` | · | · | 1 | · | · | 1 | **1** |
| **total** | 413 | 300 | 650 | 14 | 161 | 1538 | **1378** |

| predicate | prms | cgspace | porb | toc | taxonomy | total |
|---|---:|---:|---:|---:|---:|---:|
| `TAGGED_WITH` | · | · | · | · | 2865 | 2865 |
| `LOCATED_IN` | 220 | 143 | 1216 | · | · | 1579 |
| `PART_OF` | · | · | 433 | 41 | · | 474 |
| `WITH_PARTNER` | 280 | 103 | 74 | · | · | 457 |
| `AUTHORED_BY` | · | 198 | · | · | · | 198 |
| `REPORTED_UNDER` | 67 | 75 | · | 13 | · | 155 |
| `EVIDENCED_BY` | 110 | · | · | 14 | · | 124 |
| `CONTRIBUTES_TO` | 67 | · | · | 52 | · | 119 |
| `BROADER` | · | · | · | · | 108 | 108 |
| `PRODUCED_BY` | 70 | 31 | · | · | · | 101 |
| `FUNDED_BY` | · | · | 74 | · | · | 74 |
| `SYNERGY_WITH` | · | · | 20 | · | · | 20 |
| `SAME_AS` | 12 | · | · | · | · | 12 |
| `DESCRIBES` | 10 | · | · | · | · | 10 |
| `STUDIED_BY` | · | · | 1 | · | · | 1 |
| **total** | 836 | 550 | 1818 | 120 | 2973 | **6297** |

| channel | assert_object | assert_link | assert_attr | candidate_concept | total |
|---|---:|---:|---:|---:|---:|
| `prms` | 413 | 836 | 26 | 0 | 1275 |
| `cgspace` | 300 | 550 | 17 | 0 | 867 |
| `porb` | 650 | 1818 | 5 | 0 | 2473 |
| `toc` | 14 | 120 | 0 | 0 | 134 |
| `taxonomy` | 121 | 2973 | 0 | 40 | 3134 |
| **total** | 1498 | 6297 | 48 | 40 | **7883** |

**7,883 claims · 1,378 unique objects · 6,297 link claims (6,256 unique triples).** The 41 repeated triples are
deliberate: the `toc` channel re-asserts the structural spine that `porb` also derived, and both `prms` and `porb`
assert the 13 programs. In an append-only registry that is the correct behaviour — two independent channels
attesting the same fact raises `claim_count`, it does not create a second object.

**Against the WP-D targets:** results 50 ✅ · kp 77 (50 selected CGSpace items + PRMS evidence items + 13 published
PORB documents) ✅ · programs 13 ✅ · aow 5 ✅ · hlo 20 ✅ · outcomes 16 ✅ · projects 74 ✅ · melia 1 (see anomalies) ·
institutions 247 ✅ · countries 79 (target said 20–60 — the slice genuinely touches 79) · concepts 121 ✅ ·
links 6,297 ✅ (target ≥ 1,500) · **indicators 392 vs a 40–120 target** — SP01's PORB HLO sheet really has 392 KPI
rows and dropping two thirds of them would have broken the money and partner arithmetic, so they are all in.

## 3. Selection rules actually applied

### PRMS — 50 results of 776 candidates
Filter: `result.version_id = 6` (Reporting 2025) ∧ `status_id = 2` (Quality Assessed) ∧ `is_active = 1`,
reported under `results_by_inititiative.inititiative_id = 50` (SP01).

| result type | available | quota | selected |
|---|---:|---:|---:|
| Knowledge product | 447 | 12 | 12 |
| Innovation development | 112 | 10 | 10 |
| Capacity sharing for development | 118 | 8 | 8 |
| Other output | 60 | 8 | 8 |
| Innovation use | 17 | 6 | 6 |
| Other outcome | 17 | 4 | 4 |
| Policy change | 5 | 2 | 2 |
| **total** | **776** | **50** | **50** |

Within each type, rows are ordered by *(KP handle already in the CGSpace registry, has partners ∧ countries ∧
evidence, #partners, #evidence, #countries, result id)* — fully deterministic, density-first. Consequence: **all 12
selected knowledge products bridge to CGSpace**, and no selected result lacks a partner, a country or evidence.
This slice is therefore *denser than average* on purpose — it is a demo slice, not a sample for statistics.

### CGSpace — 50 items of a 540-item SP01 pool
Pool: items with `cg.contributor.programAccelerator = "Breeding for Tomorrow"` in the local WEAI harvest registry.
17 of the pool's handles were already asserted by the PRMS channel (12 KP-result handles + 5 evidence handles) and
come first; the remaining 33 are ordered by *(has abstract, has country, has affiliation, #subjects, #affiliations,
newest `dcterms.issued`, handle)*.

### PORB — the whole SP01 sheet set
`Program/Accelerator == "Breeding for Tomorrow"` on every sheet; **75 subtotal rows skipped** (any cell matching
`/\b(sub)?total\b/i`). 392 HLO rows → 392 `indicator` objects under 20 `hlo` objects in 5 `aow`; 330 Outcomes rows →
16 distinct `outcome` objects; 74 W3/Bilateral rows → 74 `project` objects; 88 Partners rows; 315 Synergy rows →
20 distinct `SYNERGY_WITH` links; 249 Countries-of-Implementation + 107 Location-of-Benefit rows resolved to
country/region links (25 "Global" rows became an attribute, 0 unresolved).

## 4. The PRMS ↔ CGSpace bridge

* 447 SP01 knowledge-product results carry a handle; **427 of those handles (95.5 %) exist in the local CGSpace
  registry** — the bridge is real at portfolio scale, not just in the demo slice.
* In the seed: **12 `SAME_AS` links** (result → kp) from the 12 selected KP results, all of which resolve.
* **17 CGSpace items were enriched rather than re-created**: their `kp` object already existed (asserted by PRMS
  under the same `trace:kp:hdl-…` id), so the CGSpace channel emitted `assert_attr` + new links only. That is the
  append-only contract working: one identity, many attesting channels.

## 5. Heuristics used (all labelled and banded, none hidden)

| # | Heuristic | Why | Where | Band |
|---|---|---|---|---|
| H1 | **result → hlo** via *(lead centre, KPI type)* from the PORB HLO sheet (top 2 HLOs by row count) | The 2025 portfolio ToC is not in the PRMS snapshot: `toc_result` has **0 rows** for initiatives 50–62, and `results_toc_result_indicators.toc_results_indicator_id` holds opaque UUIDs of the external ToC system | 67 `CONTRIBUTES_TO` links, `attrs.mapping="heuristic"` | `medium` |
| H2 | **hlo → outcome** via the shared code scheme (`HLOn.AOWy.**IOz**` ↔ `I-OC **z**.k`) | Same gap; the PORB sheets are the only place both code systems co-occur | 52 `CONTRIBUTES_TO` links, `attrs.mapping="code_heuristic"` | `medium` |
| H3 | **W3-Bilateral / MELIA row → framework target** by resolving the free-text cell to an outcome code, then an HLO code, then a title substring | The "High Level Output title" column in practice contains outcome codes (70 of 74 rows) | `FUNDED_BY`, `STUDIED_BY` with `attrs.matched_on` | `high` on code match, `medium` on title match |
| H4 | **institution name matching** — exact normalised CLARISA name, then acronym, then contained acronym | PORB and CGSpace give names, not CLARISA ids | 73 of 247 institutions stay `attrs.matched=false` | n/a (QA's `duplicate` check owns this) |
| H5 | **country resolution** — `pycountry` + a 30-entry alias table ("Côte d'Ivoire", "The Socialist Republic of Viet Nam", "The Democratic Republic of the Congo", …); UN region names become `region` objects; "Global"/"Regional" become an **attribute** (`aow.attrs.global_share_pct`), never a link | Spreadsheet geography is free text | 0 unresolved PORB geography rows | `high` |

**Not a heuristic — a rule:** the PORB **HLO budget is an attribute on the `hlo` object** (`attrs.budget_usd`,
summed over its own KPI rows; SP01 total **USD 34,012,798**) and never a link, never propagated to neighbours
(CONTRACT §3.6, Jose's money-boundary concern). A test enforces it. Partner budgets
(`WITH_PARTNER.attrs.budget_usd`) and project amounts (`FUNDED_BY.attrs.amount_usd`) stay on the row they were
reported on and are **not** summable with HLO budgets.

## 6. Taxonomy tagging (MELIAF taxonomy service, live)

* Service: `http://localhost:8420`, version **v0.2.0**, 5,960 terms; resolved with `layers = [2, 3]` (320 Lexicon +
  49 climate terms). Vendored (slimmed, sorted) copy: `data/seed/taxonomy_v0.2.0.json`.
* 630 taggable objects sent to `POST /api/resolve`; **551 came back with at least one match** →
  **2,865 `TAGGED_WITH` links** over **121 `concept` objects** plus **108 `BROADER` links** (the broader chain of every
  referenced term, walked through `parents`).
* Match quality: `pref_label` 1,727 (band `high`) · `stem` 931 · `alt_label` 207 (band `medium`).
* Coverage by type (tagged / total): result 49/50 · indicator 389/392 · outcome 15/16 · kp 69/77 · project 23/74 ·
  hlo 5/20 · melia_study 1/1. The thin HLO and project coverage is honest signal: HLO titles are three-word slogans
  ("Target markets", "Deploy seed") and project titles are funder codes — exactly the "how should this have been
  worded" gap Jules wants surfaced.
* **40 `candidate_concept` claims** — the most frequent terms from CGSpace `dcterms.subject` and PRMS result-title
  n-grams with **no** Layer-2/3 match: *rice* (18), *seed systems* (17), *seed production* (10), *varieties* (8),
  *value chains* (7), *seed quality* (6), *feed grasses* (6), *high-throughput phenotyping* (4), *urochloa* (4) …
  Each carries up to 5 contexts and an `in_layer1` flag. This is the review queue for Jules' reconciliation loop.
* If the service is down the channel falls back to local whole-word matching against the vendored export and marks
  every tag `attrs.via = "local_fallback:…"`. **Verified** by pointing `--base` at a dead port: 2,292 claims,
  544/630 objects tagged, 2,052 `TAGGED_WITH` over 106 concepts (vs 3,134 / 551 / 2,865 / 121 live — the offline
  matcher has no stemming, which is exactly the 931 `stem` matches it loses).

## 7. Anomalies and things a reviewer should know

1. **No 2025 Theory of Change offline.** `toc_result` holds 53,579 rows but none for initiatives 50–62; 696
   `results_toc_result_indicators` rows for our candidates point at external UUIDs. Kept as
   `result.attrs.toc_indicator_refs` + `toc_mapping_status="unresolved_external_uuid"` (26 `assert_attr` claims) so
   the day a ToC Explorer export lands, `ingest/toc.py` has a place to plug it in (`--toc-export`).
2. **`result_toc_impact_area_target` is empty** for these results — no impact-area-target attributes were emitted.
3. **SP01 reports exactly one MELIA study**, repeated on three identical rows (plus three subtotal rows). Content
   hashing collapses it to one `melia_study` object; that is the workbook's content, not a parser bug.
4. **`clarisa_countries_regions` is empty** in the snapshot, so `country.attrs.region` is `null`; regions come from
   `result_region` (12 objects) and from PORB region names (8 objects) instead.
5. **Innovation-use detail tables are legacy** (`results_innovations_use_measures`: 129 rows, all 2022–2023), so
   `innovation` objects exist only for the 10 Innovation-development results. Direction is
   **`DESCRIBES` innovation → result** (decision recorded in `ingest/prms.py`).
6. **Partners are reported per Area of Work**, not per HLO — the Partners sheet has no HLO column. We emit
   `WITH_PARTNER aow → institution` with `attrs.granularity="aow"` rather than inventing an HLO attribution.
7. **The slice is deliberately dense**: 0 of the 50 results lack partners, countries or evidence. Do not read
   portfolio-level data-quality conclusions off it.
8. **73 of 247 institutions are unmatched** to CLARISA (`attrs.matched=false`, ids `trace:institution:porb-…` /
   `cgspace-…`). They are left for the QA duplicate check to propose `SAME_AS` — deliberately not fuzzy-merged here.
9. **79 countries** exceeds the 20–60 planning range; SP01's PORB geography plus PRMS result countries genuinely
   span that many.
10. **Two PRMS KP handles in the selection are not in the CGSpace registry harvest** (the registry is a WEAI-scoped
    harvest, not a full mirror) — they still produce `kp` objects from the PRMS side, flagged `attrs.from_prms=true`.

## 8. Licence / openness

Every input is public CGIAR material (PRMS QA'd 2025 results, CGSpace items under their own licences, the approved
2025 PORB workbook, the MELIAF taxonomy export). The vendored extracts in `data/seed/` contain only metadata that is
already published; no full texts, no personal data beyond author names that CGSpace publishes. See
`data/seed/README.md` for the per-file detail.

# PROCESS — how TRACE Graph is maintained and sustained

This is the operator runbook. It exists because the point of TRACE is *not* a one-off graph: it is a repeatable
loop — **ingest → QA → review → publish → promote** — with every step leaving a claim behind.

All commands assume `cd ~/workspace/trace-graph` (dev) and the repo venv (`./.venv/bin/python`, written `python`
below). On the test/prod worktrees use `~/workspace/trace-graph-envs/{test,prod}`.

---

## 0. The loop in one picture

```
 source systems            intake channels           registry            graph              people/agents
 ───────────────           ───────────────           ────────            ─────              ─────────────
 PRMS snapshot     ──►  ingest/prms.py      ─┐
 CGSpace registry  ──►  ingest/cgspace.py    │   claims (jsonl)      QA gate         objects + links      UI / API / MCP
 PORB workbook     ──►  ingest/porb.py       ├─►  append-only  ──►  8 checks   ──►  materialised    ──►  explore, ask,
 results framework ──►  ingest/toc.py        │    never edited      band+status      (accepted only)      append, review
 MELIAF taxonomy   ──►  ingest/taxonomy.py  ─┘
                                                     ▲                    │
 partners / agents ──►  POST /api/claims  ────────────┘                    └──► trace-api publish → data/versions/vX.Y.Z
```

Exactly the same gate applies whether a claim comes from an intake script, the API, the UI form or an MCP agent.

---

## 1. Ingest a delta

Intake channels are **scripts, not one-offs**. Each reads a source read-only and writes a claim batch; ids are
deterministic (derived from the source primary key), so re-running an unchanged source produces byte-identical
claims and changes nothing downstream.

```bash
python -m ingest.cli all                 # all five channels in order (porb → prms → cgspace → toc → taxonomy), ~14 s
python -m ingest.prms --limit 50         # one channel; --help for flags (--db, --out, --extract, --program)
python -m ingest.taxonomy                # re-tag against the live taxonomy service and refresh the vendored export
```

Order matters: PRMS needs the PORB HLO sheet for the result→HLO heuristic, CGSpace bridges on PRMS handles, and the
taxonomy channel tags whatever the other four produced.

Cadence on this Mac: PRMS snapshot refreshes daily (`prms-prdb-daily-delta-refresh`), the CGSpace/WEAI registry
weekly, PORB per approval cycle, the taxonomy per published version.

Through the API (same result, loads straight into the registry):

```bash
curl -X POST localhost:8413/api/ingest/prms -H "X-Access-Key: $KEY" -d '{"limit": 50}'
```

If the source is not present on that machine (e.g. the prod worktree has no PRMS snapshot), the channel falls back
to replaying the committed batches and says so (`"mode": "replay-batches"`).

## 2. Load the claims and run QA

```bash
python -m app.cli load data/claims/seed-*.jsonl     # append + QA; prints accepted/review/rejected per file
python -m app.cli stats                             # counts by type, predicate, band, status, source
python -m app.cli rebuild                           # re-materialise the graph from the log (idempotent)
python -m app.cli qa-rerun                          # re-score every claim after editing qa/rules.yaml
```

`load` is idempotent: a claim id already in the registry is a no-op, so replays are safe.

**Tuning the gate.** `qa/rules.yaml` holds the band thresholds, the per-check weights, the provenance penalties, the
plausible year range and the fuzzy-duplicate threshold — including per-type overrides
(`fuzzy_duplicate_threshold_by_type`), because some types are label-identical by design (KPI lines, evidence
documents) and some have no disambiguator (authors). After any edit: `python -m app.cli qa-rerun`.

## 3. Work the review queue

```bash
curl 'localhost:8413/api/claims?status=review&limit=50' | jq '.items[] | {id, kind, subject, qa: .qa.checks}'
```

or the **Registry** page in the UI (`/registry`), which shows each failed check, the payload, the evidence and the
supersede chain. A human decides:

```bash
curl -X POST localhost:8413/api/claims/clm_…/decide -H "X-Access-Key: $KEY" \
     -d '{"decision":"accept","by":"person:j.berenguer","note":"same institution, different CLARISA spelling"}'
```

A decision is itself recorded (`decided_by`, `decided_at`, a `human_review` check) and triggers a rebuild. Claim
bodies stay immutable.

Two queues matter in practice:
* **duplicate flags** → accept (a genuine near-duplicate → propose `SAME_AS`) or reject (false positive → consider a
  per-type threshold instead of deciding the same thing 50 times);
* **candidate concepts** → free terms the taxonomy could not match. These are the input to the taxonomy loop below.

## 4. The taxonomy loop (Jules' reconciliation ask)

1. `GET /api/coverage` lists every concept with how many objects carry it, plus `unmatched_terms` — the Layer-1 terms
   with no Layer-2/3 match, with the contexts they were seen in.
2. Frequent unmatched terms are reviewed in the registry queue (`kind=candidate_concept`).
3. Accepted candidates are proposed **to the MELIAF taxonomy service** (`POST /api/terms` there — a separate service
   with its own governance: distributed input → PPT screen → Performance & Results Management steering group).
4. When that service publishes a new version, re-run `python -m ingest.taxonomy` and reload: tags are re-asserted
   against the new vocabulary and coverage moves.

## 5. Publish a version

```bash
python -m app.cli publish --bump minor --notes "…what changed and why…"
python -m app.cli export v0.1.0 graphml --out data/versions/v0.1.0.graphml
python -m app.cli export v0.1.0 csv     --out data/versions/v0.1.0.csv
git add data/versions && git commit -m "publish v0.1.0"
```

A version freezes the **accepted** graph as `data/versions/vX.Y.Z.json` (+ GraphML for Gephi/Cytoscape, + CSV for
spreadsheets). It is the citable, FAIR "data object": public, versioned, diffable. Edge ids are deterministic, so two
snapshots of the same claims are comparable line by line.

## 6. Promote across environments

```
develop ──► staging ──► main
  dev         test        prod
 :8413       :8414       :8415
```

```bash
git checkout develop && git commit …            # work happens here; CI runs on push/PR
bash scripts/deploy.sh dev                      # dev worktree = the main checkout

git -C ~/workspace/trace-graph-envs/test merge --ff-only develop
bash scripts/deploy.sh test                     # test on :8414

git -C ~/workspace/trace-graph-envs/prod merge --ff-only staging
bash scripts/deploy.sh prod                     # prod on :8415
git push origin develop staging main
```

`deploy.sh` is idempotent: it fast-forwards the branch, installs python + node deps, rebuilds the SPA, writes `.env`
(keeping the existing access key), loads the seed if the database is empty and kickstarts the launchd job, then waits
for `/health`. Nothing else is needed to deploy. Details and rollback: `docs/ENVIRONMENTS.md`.

## 7. Prove it still works

```bash
./.venv/bin/pytest -q                                            # 169 backend/ingest/contract tests
(cd frontend && npm run lint && npm test && npm run build)       # 23 vitest tests, clean build
BASE=http://127.0.0.1:8413 TRACE_ACCESS_KEY=$(cat data/access-key.txt) \
  node tests/e2e/smoke.mjs --shots /tmp/trace-shots              # 19 end-to-end checks on real data
```

CI (`.github/workflows/ci.yml`) runs the first two on every push and pull request.

## 8. Who may write

* Reads are public and unauthenticated. Writes need `X-Access-Key` (per environment, in `data/access-key.txt`,
  mode 600, never committed).
* Every claim carries `attested_by` and `provenance` ∈ {`signed`, `recorded`, `harvested`}; `signed` claims are
  HMAC-signed with a per-agent secret (`app/signing.py`) — an honest stand-in for did:web / verifiable credentials,
  labelled as such. Provenance feeds the QA score: signed > recorded > harvested.
* Anyone — CG or not — may append to any object. They may not overwrite anything. That is the governance rule:
  **QA + taxonomy + registry (who/when)**.

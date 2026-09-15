# TRACE Graph — lenses

> *"Kenya as a portfolio-level concept and Kenya attached to one result are the same node, but a
> path through it is only valid for some questions."* — Jose, 15 Sep 2026

A **lens** is a named, explainable set of allowed path patterns. Neighbourhood, path and whole-graph
queries filter every edge through the lens, so a traversal is only walked when it is meaningful for
the question being asked. Lenses live in `lenses.yaml` (editable, no code change) and are served by
`GET /api/lenses` and the MCP tool `trace_lenses`.

## How a lens is defined
```yaml
delivery:
  label: What was delivered, where and by whom
  description: >-
    Results and what they contribute to, who produced them and in which country …
  paths:
    - [result, CONTRIBUTES_TO, hlo, PART_OF, aow, PART_OF, program]
    - [result, PRODUCED_BY, institution]
```
Each consecutive `(type, PREDICATE, type)` triple becomes an allowed step. Steps are traversable in
both directions but always **reported** with their direction, so explanations read correctly
("Result X contributes to HLO Y" vs "Program W is the reporting programme of Result X").
A lens may also declare `excludes` (steps that are explicitly refused, even if some path mentions
them) and `boundary_attrs` (attributes that must not be propagated or prorated).

## The five shipped lenses

| Lens | Question it answers | Typical path |
|---|---|---|
| `portfolio` | How is the portfolio structured? | `indicator → hlo → aow → program` |
| `delivery` | What was delivered, where, by whom? | `result → hlo → aow → program`, `result → institution`, `result → country` |
| `evidence` | What evidences this, forwards and backwards? | `innovation → result → kp → concept` |
| `money` | Where does the funding sit? | `project ← FUNDED_BY ← hlo → aow → program` |
| `partnership` | Who works with whom, and where? | `institution ← result → program`, `hlo → institution`, `hlo → country` |

## Rules of the game these encode
1. **No prorating of money.** `money` deliberately excludes `result → country`,
   `result → institution` and every `TAGGED_WITH` edge. Budgets are attributes on the HLO/project
   node (`budget_usd`, `amount_usd`) and are never pushed to neighbours.
2. **Geography has levels.** `result → country` is delivery geography for *that result*;
   `hlo → country` is the portfolio-level statement from the PORB. `delivery` walks the first,
   `partnership` walks the second, and neither pretends they are the same claim.
3. **Structure is not delivery.** `portfolio` contains only `PART_OF`/`SYNERGY_WITH`, so a
   structure question can never accidentally aggregate results.
4. **Count distinct by id.** Every aggregation counts unique TRACE ids; when a node is reachable by
   more than one path, the path list is reported rather than summed.
5. **A missing path is an answer.** `GET /api/path?…&lens=money` between a result and a country
   returns `found:false` with a reason. That is the lens doing its job, not a failure.

## Explanations
`GET /api/path` returns a plain-English `explanation` built from the step list, e.g.

> Result "Market segmentation brief for groundnut in ESA" contributes to High-Level Output
> "Target markets", which is part of Area of Work "Market Intelligence", which is part of Program
> "Breeding for Tomorrow".

Phrasing per predicate (forward/inverse) is in `app/lenses.py::PREDICATE_PHRASE`; type names in
`TYPE_LABEL`. Adding a predicate means adding one line there and one path line in `lenses.yaml`.

## Adding a lens
1. Append a block to `lenses.yaml` with `label`, `description` and `paths` (plus `excludes`/`notes`).
2. Nothing else — the API, the MCP tool, the UI filter and the QA-free traversal pick it up on the
   next request (the file is cached by mtime). Add a test in `tests/test_app_graph.py` that proves
   the lens refuses what it should refuse.

# DEMO SCRIPT — ten minutes with TRACE Graph

Audience: Jules (or anyone who knows the portfolio by heart). Environment: **prod**
`https://p8415.synaptic.synapsis-analytics.com` (or `http://127.0.0.1:8415` on the Mac). Everything below is real
data from the seed slice: Science Program **SP01 "Breeding for Tomorrow"**, PRMS Reporting 2025 (Quality Assessed),
the SP01 PORB, the WEAI/CGSpace harvest and MELIAF taxonomy v0.2.0.

One sentence to open with: *"every fact here — including every arrow — arrived as a signed-or-recorded claim that
passed a quality gate; nothing was ever overwritten; the picture is a view of the log, not the truth."*

| # | Minute | Do this | Say this |
|---|---|---|---|
| 1 | 0:00 | **Explore** page, no lens. Point at the header counters: `1,310 objects · 6,247 links · 7,883 claims`. | "One slice of one programme. Colour = object type, size = degree. Right now everything is connected to everything — which is exactly Jose's complaint, so we fix it in ten seconds." |
| 2 | 0:45 | Switch the lens to **portfolio**. Then type `⌘K` → "Breeding for Tomorrow" → select `trace:program:sp01`. | "A *lens* is a named set of allowed path patterns. Portfolio = structure only: programme → area of work → high-level output → KPI." |
| 3 | 1:30 | In the drawer click **Expand neighbourhood** (depth 2). Find **Market Intelligence** (`trace:aow:sp01-aow01`), then its HLO **Steer to impact** (`trace:hlo:sp01-hlo1-aow1-io1`). Open the **Attributes** tab. | "This is the results framework from the PRMS screenshot, rebuilt as objects: SP01 → AOW01 → HLO1.AOW1.IO1. Note the budget: **USD 333,932** sits *on* the HLO. There is no budget edge — money has a boundary and is never prorated to neighbours." |
| 4 | 2:45 | Switch lens to **delivery**. In the HLO drawer open **Links** → `CONTRIBUTES_TO (in)` → open the result *"Market-driven validation protocols for rice varieties tested across South Asia and Africa by IRRI and partners"* (`trace:result:prms-22752`). | "A real 2025 PRMS result. 21 partners, 8 countries, produced by IRRI, 49 claims behind it. The result→HLO link is banded *medium* on purpose: there is no structured 2025 ToC in the snapshot, so it is a documented heuristic — the graph tells you how much to trust it." |
| 5 | 4:00 | In the drawer open the **History** tab. Scroll the claim timeline. | "Every attribute and every arrow, with who attested it, when, from which snapshot, on what evidence. A correction would appear here as a new claim superseding an old one — this is the registry, not a database row." |
| 6 | 5:00 | Open **Links** → `EVIDENCED_BY` → the CGSpace item **"IRRI NEWS"** (`trace:kp:hdl-10568-180160`). Show its `alt_ids`: handle + DOI. | "The PRMS↔CGSpace bridge. The knowledge product is one object with both identifiers; where PRMS reports a knowledge-product result with a handle, the two are joined by a `SAME_AS` claim — 12 of them in this slice." |
| 7 | 6:00 | Back on the result, **Attributes** tab → tag chips (`Smallholder farmers`, `Research`, `Partners`…). Click one → **Coverage** page. | "Tags are claims too, resolved against the live MELIAF taxonomy service on :8420 — pref-label matches band high, stem matches medium." |
| 8 | 6:45 | **Coverage** page: concepts ranked by tagged objects; then the **gaps** panel (`rice` ×18, `seed systems` ×17, `seed production` ×10). | "Layer 1 — what the text actually says — reconciled against Layer 2/3. 79% of taggable objects carry at least one approved concept; the 40 unmatched frequent terms become *candidate concepts* in the review queue and are what we propose back to the taxonomy's steering group. Only 5 of 20 HLOs resolve to any concept: their titles are slogans. That is the 'how should this have been worded' diagnostic." |
| 9 | 7:30 | **Registry** page → *Append a claim*: subject `trace:result:prms-22752`, predicate `WITH_PARTNER`, object any institution, `attested_by: partner:demo-ngo`, provenance `signed`, evidence a URL. Press **Check (dry run)**. | "Anyone — CG or not — can append to any object. They cannot overwrite anything. Here is the gate before we commit: eight deterministic checks, a score, a band. This one comes back *high → accepted*." |
| 10 | 8:15 | Remove the evidence URL and press **Check** again → the `evidence_present` check fails and the band drops. Then commit the good version and show it in the object's history. | "Same claim, weaker provenance, different band — and the rule is in `qa/rules.yaml`, editable and re-runnable over the whole log." |
| 11 | 8:45 | Filter the Registry by **status = review** (81 items). Expand one duplicate flag and one candidate concept. Accept one. | "Nothing is silently dropped. 81 items are waiting for a human: 40 candidate concepts, 28 near-duplicate objects, 9 links whose geography is outside the programme's PORB country list. Deciding is itself a claim." |
| 12 | 9:15 | **Path finder**: from the result to `trace:program:sp01` under **delivery** → one hop, plain English. Switch the lens to **money** → "no valid path". | "The lens answers *which paths are valid for this question*. Money refuses to travel from a result to a country, because that would invent a prorated budget. A refusal is an answer, with an explanation — not an error." |
| 13 | 9:45 | **API & MCP** page. Show `trace_search / trace_get / trace_path / trace_append_claim` and the one-line install. Optionally run the MCP tool from a chat client. | "Same knowledge, machine side. An agent gets the graph through MCP and writes back through the same gate as the UI. `claude mcp add --transport http trace-graph https://p8415…/mcp/`." |

## If someone asks…

* **"Where does the data come from?"** — `data/seed/SEED-REPORT.md`: 50 stratified PRMS 2025 QA'd results, 76 CGSpace
  items, the SP01 PORB workbook (20 HLOs, 392 KPI lines, 73 projects, 14 outcomes, partners, geography), the
  results-framework spine, MELIAF taxonomy v0.2.0. All public, all re-runnable: `python -m ingest.cli all` (~14 s).
* **"Is this the truth?"** — No. It is 7,883 attested claims, 7,802 of which passed the gate. Two mappings are
  heuristics and are banded `medium`; 81 claims are in review; 259 accepted links point at objects still in review
  and are therefore not drawn.
* **"Can we scale it to the whole portfolio?"** — The 13 programmes are already objects; the channels take a
  `--program` flag. The limits are the source mappings (a real ToC export would remove both heuristics), not the
  machinery.
* **"How is it maintained?"** — `PROCESS.md`: ingest deltas → load → review queue → publish a version → promote
  dev → test → prod. Three environments, CI on every push.

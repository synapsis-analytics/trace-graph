# `data/seed/` — vendored public input extracts

These files are the **inputs** of the TRACE seed, frozen so that the claim batches in `data/claims/` can be
rebuilt (and reviewed) without access to the source systems. They are produced by `ingest/*.py`; do not edit by
hand. Full method, counts and anomalies: [`SEED-REPORT.md`](SEED-REPORT.md).

| file | what it is | produced by | source system (read-only) | public? |
|---|---|---|---|---|
| `prms_sp01_results.json` | The 50 selected PRMS *Reporting 2025 / Quality Assessed* results of Science Program SP01 with their partners, centres, countries, regions, evidence links, knowledge-product handles and innovation detail — plus the 13 programs of the portfolio and the exact selection statistics. | `python -m ingest.prms` | PRMS daily snapshot `coding/PRMSDB/fresh_20260913/prdb_20260913.sqlite` (opened `file:…?mode=ro`) | Yes — QA'd results are published in the PRMS/results dashboards |
| `cgspace_sp01_items.json` | The 50 selected CGSpace items tagged `cg.contributor.programAccelerator = "Breeding for Tomorrow"`, with their full Dublin-Core/CG metadata (title, abstract, authors, affiliations, countries, subjects, SDGs, impact areas, donors, projects, licence, access rights). | `python -m ingest.cgspace` | WEAI harvest registry `weai-local-corpus/data/registry.db` (mirror of CGSpace REST) | Yes — CGSpace is an open repository; item licences are carried in `dcterms.license` |
| `porb_sp01.json` | The SP01 slice of the approved 2025 Plan of Results and Budget: 5 areas of work, 20 high-level outputs, 392 KPI rows, 16 outcomes, 74 W3/bilateral projects, 1 MELIA study, partner rows and geography shares. | `python -m ingest.porb` | `PORBs_consolidation/SummaryPORBs_v3/PORB_MASTER_All_Programs_13Aug2026.xlsx` | Yes — approved PORBs are published (CGSpace handle `10568/176124` for SP01) |
| `toc_sp01.json` | The results-framework spine actually asserted (aow/hlo/outcome `PART_OF` counts, the hlo→outcome code mapping) and the 13 published PORB documents found in CGSpace, with an explicit note on why no 2025 ToC export exists offline. | `python -m ingest.toc` | PORB extract + CGSpace registry | Yes |
| `taxonomy_v0.2.0.json` | Slimmed, id-sorted copy of the MELIAF taxonomy export `v0.2.0` (5,960 terms: 5,591 Layer-1 AI terms, 320 Layer-2 Lexicon, 49 Layer-3 climate). Fields kept: id, uri, pref_label, alt_labels, definition (≤600 chars), layer, source, status, parents, kind, path, replaced_by, notes. | `python -m ingest.taxonomy` | MELIAF taxonomy service `http://localhost:8420/api/export/current.json` | Yes — the taxonomy prototype is an open CGIAR vocabulary |
| `SEED-REPORT.md` | Counts per type/predicate/channel, selection rules, bridge statistics, heuristics, anomalies, regeneration commands. | hand-written from the run | — | Yes |

## Notes

* **Read-only sources.** Every SQLite source is opened with `sqlite3.connect("file:…?mode=ro", uri=True)`; the
  spreadsheet with `openpyxl(read_only=True, data_only=True)`. Nothing in this repo ever writes to them.
* **Refresh cadence.** The PRMS snapshot is refreshed daily on this Mac (`prms-prdb-daily-delta-refresh`), the
  CGSpace registry weekly by the WEAI collector, the PORB workbook per approval cycle, the taxonomy per published
  version. Point the channels at the newer file and re-run; TRACE ids are derived from source primary keys, so
  unchanged things keep their identity and only changed attributes generate new claims.
* **No confidential data.** All of it is public CGIAR portfolio information (Jose, 15 Sep 2026: "everything public
  and open — it is public data"). The only personal data is author names as published by CGSpace.

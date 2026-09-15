"""TRACE intake channel: **ToC / results-framework spine**.

This channel asserts the *structure* of the portfolio — the backbone every other claim hangs
off — and points each Science Program at the published PORB document that is its evidence:

* ``PART_OF``  aow → program, hlo → aow, outcome → program
* ``CONTRIBUTES_TO`` hlo → outcome (documented code heuristic, banded ``medium``)
* ``EVIDENCED_BY`` program → kp (the "Plan of Results and Budget 2025 …" item in CGSpace)
  and program → document (the PORB master workbook this slice was built from)

    python -m ingest.toc --porb-extract data/seed/porb_sp01.json --registry <registry.db> \
        --out data/claims/seed-toc.jsonl --extract data/seed/toc_sp01.json

**The 2025 portfolio Theory of Change is not available offline.** ``toc_result`` in the PRMS
snapshot holds rows only for the legacy 2022–2024 initiatives (ids 1–41); for the new Science
Programs the ToC lives in the separate ToC Explorer/Tracker system and PRMS only stores opaque
indicator UUIDs. This channel is therefore the **plug point**: when a ToC Explorer export is
available, drop it in as ``--toc-export`` and the structural claims below are replaced by
sourced ones. Until then the spine comes from the PORB workbook and the hlo→outcome mapping is
a heuristic on the shared code scheme (``HLOn.AOWy.IOz`` ↔ ``I-OC z.k``), which we band
``medium`` and label ``attrs.mapping="code_heuristic"``.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from ingest import common as C
from ingest.porb import PROGRAM_CODES
from ingest.prms import connect_ro, handle_id, norm_handle

CHANNEL = "toc"
SYSTEM = "toc"

DEFAULT_REGISTRY = "/Users/smithai/workspace/weai-local-corpus/data/registry.db"
PORB_TITLE_LIKE = "Plan of Results and Budget 2025%"
IO_RE = re.compile(r"IO(\d+)\s*$", re.I)
OC_NUM_RE = re.compile(r"^(?:I-OC|EOI-OC)\s*(\d+)\.")


def find_porb_documents(registry: str) -> list[dict[str, Any]]:
    """The published PORB documents in CGSpace (public, one per Science Program)."""
    if not Path(registry).exists():
        return []
    con = connect_ro(registry)
    try:
        rows = con.execute(
            """select i.uuid, i.handle, i.name, i.dcterms_issued
               from items i
               join metadata_values m on m.uuid = i.uuid
               where m.metadata_key = 'dc.title' and m.value like ?
               group by i.uuid order by i.handle""", (PORB_TITLE_LIKE,)).fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        title = r["name"] or ""
        m = re.search(r"\bon\s+(.+?)\s*$", title)
        prog_name = (m.group(1) if m else "").strip()
        code = PROGRAM_CODES.get(prog_name.lower())
        out.append({"uuid": r["uuid"], "handle": norm_handle(r["handle"]) or r["handle"],
                    "title": title, "issued": r["dcterms_issued"],
                    "program_name": prog_name, "program_code": code})
    return out


def run(porb_extract: str, registry: str, out: str, extract: str,
        porb_xlsx: str | None = None, toc_export: str | None = None) -> dict[str, Any]:
    data = json.loads(Path(porb_extract).read_text(encoding="utf-8")) if Path(porb_extract).exists() else {}
    program_code = (data.get("program") or {}).get("code", "SP01")
    program_name = (data.get("program") or {}).get("name", "Breeding for Tomorrow")
    snapshot = data.get("snapshot", "porb_master")
    prog_id = C.make_id("program", program_code.lower())

    claims: list[dict[str, Any]] = []
    seen: set[str] = set()

    def obj(*args, ref: str, **kwargs) -> str:
        claim = C.object_claim(*args, channel=CHANNEL, system=SYSTEM, ref=ref,
                               snapshot=snapshot, **kwargs)
        oid = claim["payload"]["id"]
        if oid not in seen:
            seen.add(oid)
            claims.append(claim)
        return oid

    def link(subject: str, predicate: str, target: str, ref: str, **kwargs) -> None:
        claims.append(C.link_claim(subject, predicate, target, channel=CHANNEL, system=SYSTEM,
                                   ref=ref, snapshot=snapshot, **kwargs))

    if toc_export and Path(toc_export).exists():  # pragma: no cover - future plug point
        raise SystemExit("--toc-export is the documented plug point but no export exists yet; "
                         "remove the flag to use the PORB-derived spine.")

    aows = data.get("aows", [])
    hlos = data.get("hlos", [])
    outcomes = data.get("outcomes", [])

    # --- structural spine -------------------------------------------------------------
    for a in aows:
        link(a["id"], "PART_OF", prog_id, f"results framework: {a['code']} of {program_code}",
             attrs={"level": "aow", "spine": True}, band="high")
    aow_by_code = {a["code"]: a["id"] for a in aows}
    for h in hlos:
        aid = aow_by_code.get(h.get("aow_code"))
        if aid:
            link(h["id"], "PART_OF", aid, f"results framework: {h.get('code')} under {h['aow_code']}",
                 attrs={"level": "hlo", "spine": True}, band="high")
    for o in outcomes:
        link(o["id"], "PART_OF", prog_id,
             f"results framework: outcome {o.get('code') or o['label'][:40]}",
             attrs={"level": "outcome", "spine": True}, band="high")

    # --- hlo -> outcome (code heuristic) ----------------------------------------------
    by_io: dict[str, list[dict[str, Any]]] = {}
    for o in outcomes:
        m = OC_NUM_RE.match((o.get("code") or "").upper())
        if m:
            by_io.setdefault(m.group(1), []).append(o)
    mapped = 0
    for h in hlos:
        m = IO_RE.search((h.get("code") or ""))
        if not m:
            continue
        for o in by_io.get(m.group(1), []):
            mapped += 1
            link(h["id"], "CONTRIBUTES_TO", o["id"],
                 f"code heuristic: {h['code']} -> {o['code']}",
                 attrs={"mapping": "code_heuristic",
                        "rule": "HLOn.AOWy.IOz contributes to interim outcomes I-OC z.*",
                        "hlo_code": h.get("code"), "outcome_code": o.get("code")},
                 band="medium",
                 note="No ToC Explorer export available offline; see docs/DATA-MODEL.md.")

    # --- program -> published PORB document -------------------------------------------
    docs = find_porb_documents(registry)
    linked_docs = 0
    for d in docs:
        if not d["program_code"] or not d["handle"]:
            continue
        kid = handle_id(d["handle"])
        obj("kp", kid, d["title"], ref=f"CGSpace items.handle={d['handle']}",
            description=f"Published Plan of Results and Budget 2025 for {d['program_name']}.",
            attrs={"handle": d["handle"], "uri": f"https://hdl.handle.net/{d['handle']}",
                   "type": "Report", "issued": d["issued"], "is_porb_document": True,
                   "program_code": d["program_code"], "cgspace_uuid": d["uuid"]},
            alt_ids=[{"scheme": "cgspace_handle", "value": d["handle"]},
                     {"scheme": "cgspace_uuid", "value": d["uuid"]}],
            evidence=[{"kind": "handle", "value": d["handle"]}])
        pid = C.make_id("program", d["program_code"].lower())
        link(pid, "EVIDENCED_BY", kid, f"CGSpace title search '{PORB_TITLE_LIKE}'",
             attrs={"document_kind": "Plan of Results and Budget 2025"}, band="high",
             evidence=[{"kind": "handle", "value": d["handle"]}])
        link(kid, "REPORTED_UNDER", pid, f"CGSpace items.handle={d['handle']}",
             attrs={"via": "PORB document title"}, band="high")
        linked_docs += 1

    # --- the PORB master workbook itself, as a citable document -----------------------
    if porb_xlsx:
        did = C.make_id("document", "porb-master-" + C.sha1_12(Path(porb_xlsx).name))
        obj("document", did, Path(porb_xlsx).name, ref=porb_xlsx,
            description="Consolidated master workbook of the approved 2025 Plans of Results and "
                        "Budget for all 13 CGIAR Science Programs and Accelerators.",
            attrs={"file_name": Path(porb_xlsx).name, "kind": "workbook", "public": True,
                   "sheets": ["HLO", "Partners", "W3-Bilateral", "MELIA", "Cross Cutting",
                              "Outcomes", "Synergy Programs", "Countries of Implementation",
                              "Location of Benefit", "Anaplan"]},
            alt_ids=[{"scheme": "file", "value": Path(porb_xlsx).name}])
        link(prog_id, "EVIDENCED_BY", did, porb_xlsx,
             attrs={"document_kind": "PORB master workbook"}, band="high",
             evidence=[{"kind": "file", "value": Path(porb_xlsx).name}])

    claims = C.dedupe_links(C.dedupe_objects(claims))

    C.write_extract(extract, {
        "channel": CHANNEL, "snapshot": snapshot, "public": True,
        "program": {"code": program_code, "name": program_name},
        "generated_at": C.now_iso(),
        "toc_export_available": False,
        "toc_note": ("PRMS toc_result holds no rows for initiatives 50-62 (the 2025 Science "
                     "Programs); results_toc_result_indicators stores opaque external UUIDs. "
                     "The spine below is derived from the PORB workbook."),
        "counts": {"aow_part_of": len(aows), "hlo_part_of": len(hlos),
                   "outcome_part_of": len(outcomes), "hlo_contributes_to": mapped,
                   "porb_documents": linked_docs},
        "porb_documents": docs,
    })
    n = C.write_batch(out, claims)
    summary = C.summarise(claims)
    summary.update(channel=CHANNEL, out=out, extract=extract, claims=n)
    return summary


def run_channel(limit: int | None = None, load: bool = True, out: str | None = None,
                toc_export: str | None = None, **_: object) -> dict:
    """Keyword-only entry point for POST /api/ingest/toc (PLAN §4). `limit` is ignored: the
    results-framework spine is a whole or nothing."""
    out_path = C.channel_out_path(CHANNEL, out)
    return C.channel_entry(CHANNEL, lambda: run(
        "data/seed/porb_sp01.json", DEFAULT_REGISTRY, out_path,
        C.runtime_extract_path(CHANNEL), None, toc_export), load=load)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="TRACE intake channel: ToC / results framework")
    ap.add_argument("--porb-extract", default="data/seed/porb_sp01.json")
    ap.add_argument("--registry", default=DEFAULT_REGISTRY)
    ap.add_argument("--out", default="data/claims/seed-toc.jsonl")
    ap.add_argument("--extract", default="data/seed/toc_sp01.json")
    ap.add_argument("--porb-xlsx", default=None)
    ap.add_argument("--toc-export", default=None)
    a = ap.parse_args(argv)
    s = run(a.porb_extract, a.registry, a.out, a.extract, a.porb_xlsx, a.toc_export)
    print(f"[toc] {s['claims']} claims -> {s['out']}")
    print(f"      objects: {s['objects']}")
    print(f"      links:   {s['links']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

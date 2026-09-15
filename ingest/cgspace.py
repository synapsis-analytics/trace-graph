"""TRACE intake channel: **CGSpace** (via the local WEAI harvest registry).

Emits ``kp`` (knowledge product) objects for the Science Program's CGSpace items, with their
geography, affiliations, funders, authors and programme tagging — and, critically, the
**PRMS ↔ CGSpace bridge**: items whose handle already appeared in the PRMS batch are not
re-asserted as new objects, only enriched (``assert_attr`` + new links), which is exactly the
append-only behaviour the registry is supposed to have.

    python -m ingest.cgspace --registry <registry.db> --program "Breeding for Tomorrow" \
        --limit 50 --bridge data/seed/prms_sp01_results.json \
        --out data/claims/seed-cgspace.jsonl --extract data/seed/cgspace_sp01_items.json

Assumptions:

* An affiliation is treated as a **CGIAR centre** when it matches a CLARISA institution that is
  a centre (``center_code`` present or institution type 54) or one of the known centre acronyms;
  those get ``PRODUCED_BY``, everyone else ``WITH_PARTNER`` (CONTRACT §3.3).
* Unmatched affiliation names become ``trace:institution:cgspace-<slug>`` with ``attrs.matched=false``
  so the QA duplicate check can later propose a ``SAME_AS`` to a CLARISA institution.
* ``person`` objects are keyed by a slug of the author name (authority ids are not in the
  registry); max 5 authors per item, as instructed.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from ingest import common as C
from ingest.prms import norm_handle, handle_id, connect_ro

CHANNEL = "cgspace"
SYSTEM = "cgspace"

DEFAULT_REGISTRY = "/Users/smithai/workspace/weai-local-corpus/data/registry.db"

CENTRE_ACRONYMS = {
    "africarice", "bioversity", "ciat", "cimmyt", "cip", "icarda", "icraf", "icrisat",
    "ifpri", "iita", "ilri", "irri", "iwmi", "worldfish", "cifor", "cgiar",
    "alliance of bioversity international and ciat", "alliance bioversity ciat",
}

KEYS = {
    "title": "dc.title",
    "abstract": "dcterms.abstract",
    "uri": "dc.identifier.uri",
    "doi": "cg.identifier.doi",
    "program": "cg.contributor.programAccelerator",
    "affiliation": "cg.contributor.affiliation",
    "country": "cg.coverage.country",
    "iso2": "cg.coverage.iso3166-alpha2",
    "region": "cg.coverage.region",
    "subject": "dcterms.subject",
    "impact_area": "cg.subject.impactArea",
    "sdg": "cg.subject.sdg",
    "type": "dcterms.type",
    "author": "dc.contributor.author",
    "donor": "cg.contributor.donor",
    "project": "cg.identifier.project",
    "license": "dcterms.license",
    "access_rights": "dcterms.accessRights",
    "review_status": "cg.reviewStatus",
    "issued": "dcterms.issued",
    "publisher": "dcterms.publisher",
    "initiative": "cg.contributor.initiative",
    "citation": "dcterms.bibliographicCitation",
}


def fetch_items(con: sqlite3.Connection, program: str) -> dict[str, dict[str, Any]]:
    uuids = [r[0] for r in con.execute(
        "select distinct uuid from metadata_values where metadata_key = ? and value = ?",
        (KEYS["program"], program))]
    if not uuids:
        return {}
    items: dict[str, dict[str, Any]] = {}
    for chunk in (uuids[i:i + 500] for i in range(0, len(uuids), 500)):
        ph = ",".join("?" * len(chunk))
        for r in con.execute(
                f"""select uuid, handle, name, dcterms_issued, text_extraction_status, lastModified
                    from items where uuid in ({ph})""", chunk):
            items[r["uuid"]] = {
                "uuid": r["uuid"], "handle": norm_handle(r["handle"]) or r["handle"],
                "name": r["name"], "issued": r["dcterms_issued"],
                "has_fulltext": r["text_extraction_status"] == "extracted",
                "last_modified": r["lastModified"], "meta": defaultdict(list),
            }
        for r in con.execute(
                f"""select uuid, metadata_key, value from metadata_values
                    where uuid in ({ph}) order by metadata_key, place""", chunk):
            if r["uuid"] in items and r["value"]:
                items[r["uuid"]]["meta"][r["metadata_key"]].append(str(r["value"]).strip())
    return items


def _m(item: dict[str, Any], key: str) -> list[str]:
    return item["meta"].get(KEYS[key], [])


def _m1(item: dict[str, Any], key: str) -> str | None:
    vals = _m(item, key)
    return vals[0] if vals else None


def select_items(items: dict[str, dict[str, Any]], limit: int,
                 bridge_handles: set[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Bridge items first, then dense recent items with an abstract (deterministic)."""
    def key(it: dict[str, Any]) -> tuple:
        recency = str(it.get("issued") or "0000")
        return (
            -(1 if _m(it, "abstract") else 0),
            -(1 if _m(it, "iso2") or _m(it, "country") else 0),
            -(1 if _m(it, "affiliation") else 0),
            -min(len(_m(it, "subject")), 12),
            -min(len(_m(it, "affiliation")), 10),
            "".join(chr(0x10FFFD - ord(c)) for c in recency),  # newest issued date first
            it["handle"] or it["uuid"],
        )

    bridged = sorted((it for it in items.values() if it["handle"] in bridge_handles), key=key)
    rest = sorted((it for it in items.values() if it["handle"] not in bridge_handles), key=key)
    chosen = (bridged + rest)[:limit]
    stats = {
        "pool": len(items),
        "bridge_candidates_in_registry": len(bridged),
        "bridged_selected": sum(1 for it in chosen if it["handle"] in bridge_handles),
        "rule": ("every SP01 item whose handle is already in the PRMS batch first, then items "
                 "ordered by (has abstract, has country, has affiliation, #subjects, "
                 "#affiliations, newest issued date, handle)"),
    }
    return chosen, stats


def run(registry: str, program: str, limit: int, bridge: str, out: str,
        extract: str) -> dict[str, Any]:
    snapshot = "weai_registry_" + Path(registry).stat().st_mtime.__int__().__str__()
    con = connect_ro(registry)
    try:
        items = fetch_items(con, program)
    finally:
        con.close()

    # --- bridge: handles already asserted by the PRMS channel --------------------------
    bridge_handles: set[str] = set()
    prms_institutions: list[dict[str, Any]] = []
    if bridge and Path(bridge).exists():
        data = json.loads(Path(bridge).read_text(encoding="utf-8"))
        for r in data.get("results", []):
            h = norm_handle(r.get("kp_handle"))
            if h:
                bridge_handles.add(h)
            for e in r.get("evidence", []) or []:
                if e.get("handle"):
                    bridge_handles.add(e["handle"])
        prms_institutions = C.load_prms_institutions(bridge)
    matcher = C.InstitutionMatcher(prms_institutions)

    chosen, stats = select_items(items, limit, bridge_handles)

    program_code = None
    from ingest.porb import PROGRAM_CODES
    program_code = PROGRAM_CODES.get(program.lower().strip(), "SP01")

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

    def affiliation_obj(name: str, ref: str) -> tuple[str, bool]:
        hit = matcher.match(name)
        if hit and hit.get("clarisa_id"):
            iid = C.make_id("institution", f"clarisa-{hit['clarisa_id']}")
            is_centre = bool(hit.get("center_code")) or hit.get("type_code") == 54 or \
                (hit.get("acronym") or "").lower() in CENTRE_ACRONYMS
            obj("institution", iid, hit.get("name") or name, ref=ref,
                attrs={"acronym": hit.get("acronym"), "matched": True,
                       "matched_via": "clarisa name/acronym", "cgspace_name": name,
                       "is_cgiar_centre": is_centre},
                alt_ids=[{"scheme": "clarisa_institution_id", "value": str(hit["clarisa_id"])}])
            return iid, is_centre
        low = name.lower()
        is_centre = any(a in low for a in CENTRE_ACRONYMS)
        iid = C.make_id("institution", f"cgspace-{C.slugify(name)}")
        obj("institution", iid, name, ref=ref,
            attrs={"matched": False, "cgspace_name": name, "is_cgiar_centre": is_centre},
            alt_ids=[{"scheme": "cgspace_affiliation", "value": name}])
        return iid, is_centre

    bridged_enriched = 0
    for it in chosen:
        handle = it["handle"]
        kid = handle_id(handle) if handle else C.make_id("kp", "uuid-" + C.sha1_12(it["uuid"]))
        ref = f"items.handle={handle}"
        attrs = {
            "title": C.trim(_m1(it, "title") or it["name"], 500),
            "abstract": C.trim(_m1(it, "abstract"), 2000),
            "type": _m1(it, "type"),
            "issued": _m1(it, "issued") or it.get("issued"),
            "doi": _m1(it, "doi"),
            "uri": _m1(it, "uri") or (f"https://hdl.handle.net/{handle}" if handle else None),
            "handle": handle,
            "license": _m1(it, "license"),
            "access_rights": _m1(it, "access_rights"),
            "review_status": _m1(it, "review_status"),
            "publisher": _m1(it, "publisher"),
            "subjects": _m(it, "subject")[:25],
            "impact_areas": _m(it, "impact_area"),
            "sdgs": _m(it, "sdg"),
            "donors": _m(it, "donor")[:15],
            "project_ids": _m(it, "project")[:10],
            "programs": _m(it, "program"),
            "initiatives": _m(it, "initiative")[:10],
            "regions": _m(it, "region"),
            "countries": _m(it, "country"),
            "has_fulltext": it["has_fulltext"],
            "cgspace_uuid": it["uuid"],
            "from_cgspace": True,
        }
        alt_ids = [{"scheme": "cgspace_handle", "value": handle},
                   {"scheme": "cgspace_uuid", "value": it["uuid"]}]
        if attrs["doi"]:
            alt_ids.append({"scheme": "doi", "value": attrs["doi"]})

        if handle in bridge_handles:
            # already asserted by the PRMS channel -> enrich, never re-create (append-only)
            bridged_enriched += 1
            claims.append(C.attr_claim(kid, attrs, channel=CHANNEL, system=SYSTEM, ref=ref,
                                       snapshot=snapshot, band="high",
                                       evidence=[{"kind": "handle", "value": handle}],
                                       note="PRMS↔CGSpace bridge: enriching an object the PRMS "
                                            "channel already asserted under the same handle."))
        else:
            obj("kp", kid, attrs["title"] or handle, ref=ref, description=attrs["abstract"],
                attrs=attrs, alt_ids=alt_ids,
                evidence=[{"kind": "handle", "value": handle}] if handle else None)

        # REPORTED_UNDER: kp -> program
        for prog_name in _m(it, "program"):
            code = PROGRAM_CODES.get(prog_name.lower().strip())
            if code:
                link(kid, "REPORTED_UNDER", C.make_id("program", code.lower()), ref,
                     attrs={"via": "cg.contributor.programAccelerator", "program": prog_name},
                     band="high")

        # LOCATED_IN: ISO2 coverage
        isos = {v.strip().upper() for v in _m(it, "iso2") if len(v.strip()) == 2}
        for name in _m(it, "country"):
            iso = C.country_iso2(name)
            if iso:
                isos.add(iso)
        for iso in sorted(isos):
            cid = C.make_id("country", iso.lower())
            obj("country", cid, C.country_name(iso), ref=ref, attrs={"iso2": iso},
                alt_ids=[{"scheme": "iso2", "value": iso}])
            link(kid, "LOCATED_IN", cid, ref, attrs={"kind": "country",
                                                     "via": "cg.coverage.iso3166-alpha2"})

        # PRODUCED_BY / WITH_PARTNER: affiliations
        for name in _m(it, "affiliation")[:12]:
            iid, is_centre = affiliation_obj(name, ref)
            link(kid, "PRODUCED_BY" if is_centre else "WITH_PARTNER", iid, ref,
                 attrs={"via": "cg.contributor.affiliation", "affiliation": name})

        # AUTHORED_BY: max 5 authors
        for author in _m(it, "author")[:5]:
            pid = C.make_id("person", C.slugify(author))
            obj("person", pid, author, ref=ref, attrs={"name": author, "source": "cgspace"},
                alt_ids=[{"scheme": "cgspace_author", "value": author}])
            link(kid, "AUTHORED_BY", pid, ref, attrs={"via": "dc.contributor.author"})

    claims = C.dedupe_links(C.dedupe_objects(claims))

    C.write_extract(extract, {
        "channel": CHANNEL, "snapshot": snapshot, "source_file": registry, "public": True,
        "program": {"name": program, "code": program_code}, "generated_at": C.now_iso(),
        "selection": {**stats, "bridge_handles_from_prms": len(bridge_handles),
                      "bridged_enriched": bridged_enriched},
        "items": [{k: (dict(v) if k == "meta" else v) for k, v in it.items()} for it in chosen],
    })
    n = C.write_batch(out, claims)
    summary = C.summarise(claims)
    summary.update(channel=CHANNEL, out=out, extract=extract, claims=n,
                   bridged=bridged_enriched, selection=stats)
    return summary


def run_channel(limit: int | None = None, load: bool = True, out: str | None = None,
                program: str = "Breeding for Tomorrow", **_: object) -> dict:
    """Keyword-only entry point for POST /api/ingest/cgspace (PLAN §4)."""
    out_path = C.channel_out_path(CHANNEL, out)
    return C.channel_entry(CHANNEL, lambda: run(
        DEFAULT_REGISTRY, program, int(limit or 50), "data/seed/prms_sp01_results.json",
        out_path, C.runtime_extract_path(CHANNEL)), load=load)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="TRACE intake channel: CGSpace")
    ap.add_argument("--registry", default=DEFAULT_REGISTRY)
    ap.add_argument("--program", default="Breeding for Tomorrow")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--bridge", default="data/seed/prms_sp01_results.json")
    ap.add_argument("--out", default="data/claims/seed-cgspace.jsonl")
    ap.add_argument("--extract", default="data/seed/cgspace_sp01_items.json")
    a = ap.parse_args(argv)
    s = run(a.registry, a.program, a.limit, a.bridge, a.out, a.extract)
    print(f"[cgspace] {s['claims']} claims -> {s['out']} (bridged/enriched: {s['bridged']})")
    print(f"          objects: {s['objects']}")
    print(f"          links:   {s['links']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

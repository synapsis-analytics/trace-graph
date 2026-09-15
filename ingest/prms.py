"""TRACE intake channel: **PRMS** (CGIAR Performance and Results Management System).

Reads the daily PRMS snapshot (SQLite, opened strictly read-only) and emits claims for a
stratified slice of Science-Program results plus everything they hang off: programs,
institutions, countries, regions, evidence documents, knowledge products and innovations.

    python -m ingest.prms --db <sqlite> --program SP01 --limit 50 \
        --out data/claims/seed-prms.jsonl --extract data/seed/prms_sp01_results.json

Assumptions (documented in data/seed/SEED-REPORT.md):

* *Reporting 2025* = ``result.version_id = 6``; *Quality Assessed* = ``result.status_id = 2``.
* The 2025 portfolio Theory of Change is **not in this snapshot**: ``toc_result`` holds no row
  for initiatives 50–62 and ``results_toc_result_indicators.toc_results_indicator_id`` is an
  opaque UUID from the (external) ToC system.  We therefore keep the UUIDs as evidence and map
  ``result -> hlo`` with the documented **heuristic** (lead centre + KPI type from the PORB HLO
  sheet), banded ``medium`` with ``attrs.mapping = "heuristic"``.
* ``innovation`` objects exist for Innovation-development results only (``results_innovations_dev``);
  the 2025 innovation-use detail tables are legacy/empty.  Link direction is
  **``DESCRIBES`` innovation -> result** (chosen over ``PART_OF``: the innovation record
  *describes* the reported result, and DESCRIBES is already in the CONTRACT §3.3 table).
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ingest import common as C

CHANNEL = "prms"
SYSTEM = "prms"

DEFAULT_DB = "/Users/smithai/workspace/coding/PRMSDB/fresh_20260913/prdb_20260913.sqlite"
DEFAULT_REGISTRY = "/Users/smithai/workspace/weai-local-corpus/data/registry.db"

VERSION_ID = 6          # "Reporting 2025"
STATUS_QA = 2           # "Quality Assessed"

# Stratification quotas (CONTRACT §6; sums to 50)
QUOTAS: dict[str, int] = {
    "Knowledge product": 12,
    "Innovation development": 10,
    "Capacity sharing for development": 8,
    "Other output": 8,
    "Innovation use": 6,
    "Other outcome": 4,
    "Policy change": 2,
}

# PRMS result type -> PORB "KPI Type" (used by the result->HLO heuristic)
KPI_OF_RESULT_TYPE = {
    "Knowledge product": "Number of knowledge products",
    "Innovation development": "Number of innovations (innovation development)",
    "Capacity sharing for development": "Number of people trained (capacity sharing for development)",
}

TAG_LEVELS = {1: "Not targeted", 2: "Significant", 3: "Principal"}

HANDLE_RE = re.compile(r"(?:hdl\.handle\.net|cgspace\.cgiar\.org/handle|hdl\.net)/(\d+/\d+)", re.I)
BARE_HANDLE_RE = re.compile(r"^\s*(\d+/\d+)\s*$")


def norm_handle(value: str | None) -> str | None:
    """Normalise anything that looks like a CGSpace handle to ``10568/123456``."""
    if not value:
        return None
    m = HANDLE_RE.search(str(value)) or BARE_HANDLE_RE.match(str(value))
    return m.group(1) if m else None


def handle_id(handle: str) -> str:
    return C.make_id("kp", "hdl-" + handle.replace("/", "-"))


def connect_ro(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


# --------------------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------------------
def fetch_programs(con: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = con.execute(
        "select id, official_code, name, short_name from clarisa_initiatives "
        "where id between 50 and 62 order by id"
    ).fetchall()
    return [
        {
            "initiative_id": r["id"],
            "code": (r["official_code"] or "").strip(),
            "name": (r["name"] or r["short_name"] or "").replace("\xa0", " ").strip(),
        }
        for r in rows
    ]


def candidate_results(con: sqlite3.Connection, initiative_id: int) -> list[dict[str, Any]]:
    sql = """
        select r.id, r.title, r.description, r.result_code, r.result_type_id,
               rt.name as result_type, r.status_id, r.is_krs, r.krs_url,
               r.gender_tag_level_id, r.climate_change_tag_level_id, r.nutrition_tag_level_id,
               r.environmental_biodiversity_tag_level_id, r.poverty_tag_level_id,
               r.geographic_scope_id, r.last_updated_date,
               (select count(*) from results_by_institution i
                  where i.result_id = r.id and i.is_active = 1) as n_inst,
               (select count(*) from result_country c
                  where c.result_id = r.id and c.is_active = 1) as n_country,
               (select count(*) from evidence e
                  where e.result_id = r.id and e.is_active = 1 and e.link is not null) as n_evidence,
               (select count(*) from result_region g
                  where g.result_id = r.id and g.is_active = 1) as n_region,
               kp.handle as kp_handle, kp.doi as kp_doi, kp.knowledge_product_type as kp_type,
               kp.licence as kp_licence, kp.findable, kp.accesible, kp.interoperable, kp.reusable
        from result r
        join results_by_inititiative rbi
             on rbi.result_id = r.id and rbi.is_active = 1 and rbi.inititiative_id = ?
        join result_type rt on rt.id = r.result_type_id
        left join results_knowledge_product kp on kp.results_id = r.id and kp.is_active = 1
        where r.version_id = ? and r.status_id = ? and r.is_active = 1
    """
    return [dict(r) for r in con.execute(sql, (initiative_id, VERSION_ID, STATUS_QA))]


def registry_handles(path: str) -> set[str]:
    """Handles present in the local CGSpace/WEAI registry (used to prefer bridgeable KPs)."""
    if not Path(path).exists():
        return set()
    con = connect_ro(path)
    try:
        return {r[0] for r in con.execute("select handle from items where handle is not null")}
    finally:
        con.close()


def select_results(cands: list[dict[str, Any]], limit: int, in_registry: set[str],
                   quotas: dict[str, int] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Stratified, density-first, deterministic selection (CONTRACT §6)."""
    quotas = dict(quotas or QUOTAS)
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in cands:
        by_type[c["result_type"]].append(c)

    def rank(c: dict[str, Any]) -> tuple:
        bridged = 1 if (norm_handle(c.get("kp_handle")) or "") in in_registry else 0
        dense = (1 if c["n_inst"] else 0) + (1 if c["n_country"] else 0) + (1 if c["n_evidence"] else 0)
        return (-bridged, -dense, -min(c["n_inst"], 12), -min(c["n_evidence"], 6),
                -min(c["n_country"], 8), c["id"])

    chosen: list[dict[str, Any]] = []
    applied: dict[str, int] = {}
    for rtype, want in quotas.items():
        pool = sorted(by_type.get(rtype, []), key=rank)
        take = pool[:want]
        applied[rtype] = len(take)
        chosen.extend(take)
    # Top-up (or trim) to exactly `limit`, respecting density order across all types.
    if len(chosen) < limit:
        picked = {c["id"] for c in chosen}
        rest = sorted((c for c in cands if c["id"] not in picked), key=rank)
        chosen.extend(rest[: limit - len(chosen)])
    chosen = sorted(chosen, key=rank)[:limit]
    stats = {
        "available_by_type": dict(Counter(c["result_type"] for c in cands)),
        "quotas": quotas,
        "selected_by_type": dict(Counter(c["result_type"] for c in chosen)),
        "bridged_kp_handles": sum(
            1 for c in chosen if (norm_handle(c.get("kp_handle")) or "") in in_registry),
        "rule": ("stratified by result_type using the quotas above; within a type ordered by "
                 "(handle present in the CGSpace registry, has partners+countries+evidence, "
                 "#partners, #evidence, #countries, result id) — deterministic"),
    }
    return sorted(chosen, key=lambda c: c["id"]), stats


def enrich(con: sqlite3.Connection, results: list[dict[str, Any]]) -> None:
    """Attach institutions, centres, countries, regions, evidence, innovation, ToC refs."""
    ids = [r["id"] for r in results]
    ph = ",".join("?" * len(ids))
    index = {r["id"]: r for r in results}
    for r in results:
        r.update(institutions=[], centres=[], countries=[], regions=[], evidence=[],
                 innovation=None, toc_indicator_uuids=[], initiatives=[])

    for row in con.execute(
        f"""select rbi.result_id, rbi.institutions_id, rbi.institution_roles_id, rbi.is_leading_result,
                   ir.name as role_name, ci.name, ci.acronym, ci.institution_type_code,
                   ci.headquarter_country_iso2, cit.name as type_name
            from results_by_institution rbi
            join clarisa_institutions ci on ci.id = rbi.institutions_id
            left join institution_role ir on ir.id = rbi.institution_roles_id
            left join clarisa_institution_types cit on cit.code = ci.institution_type_code
            where rbi.result_id in ({ph}) and rbi.is_active = 1""", ids):
        index[row["result_id"]]["institutions"].append({
            "clarisa_id": row["institutions_id"],
            "name": (row["name"] or "").strip(),
            "acronym": (row["acronym"] or "").strip() or None,
            "type": row["type_name"],
            "type_code": row["institution_type_code"],
            "hq_country_iso2": (row["headquarter_country_iso2"] or "").upper() or None,
            "role": row["role_name"],
            "is_leading": bool(row["is_leading_result"]),
        })

    for row in con.execute(
        f"""select rc.result_id, rc.is_primary, rc.is_leading_result, ci.id as clarisa_id,
                   ci.name, ci.acronym, ci.headquarter_country_iso2, cc.code
            from results_center rc
            join clarisa_center cc on cc.code = rc.center_id
            join clarisa_institutions ci on ci.id = cc.institutionId
            where rc.result_id in ({ph}) and rc.is_active = 1""", ids):
        index[row["result_id"]]["centres"].append({
            "clarisa_id": row["clarisa_id"], "center_code": row["code"],
            "name": (row["name"] or "").strip(), "acronym": (row["acronym"] or "").strip(),
            "hq_country_iso2": (row["headquarter_country_iso2"] or "").upper() or None,
            "is_primary": bool(row["is_primary"]), "is_leading": bool(row["is_leading_result"]),
        })

    for row in con.execute(
        f"""select rc.result_id, cc.id as clarisa_id, cc.name, cc.iso_alpha_2, cc.iso_alpha_3
            from result_country rc join clarisa_countries cc on cc.id = rc.country_id
            where rc.result_id in ({ph}) and rc.is_active = 1""", ids):
        if row["iso_alpha_2"]:
            index[row["result_id"]]["countries"].append({
                "clarisa_id": row["clarisa_id"], "name": (row["name"] or "").strip(),
                "iso2": row["iso_alpha_2"].upper(), "iso3": (row["iso_alpha_3"] or "").upper() or None,
            })

    for row in con.execute(
        f"""select rr.result_id, cr.um49Code as code, cr.name
            from result_region rr join clarisa_regions cr on cr.um49Code = rr.region_id
            where rr.result_id in ({ph}) and rr.is_active = 1""", ids):
        index[row["result_id"]]["regions"].append(
            {"um49": row["code"], "name": (row["name"] or "").strip()})

    for row in con.execute(
        f"""select e.result_id, e.link, e.description, e.evidence_type_id, et.name as type_name,
                   e.is_supplementary, e.knowledge_product_related
            from evidence e left join evidence_types et on et.id = e.evidence_type_id
            where e.result_id in ({ph}) and e.is_active = 1 and e.link is not null""", ids):
        index[row["result_id"]]["evidence"].append({
            "link": (row["link"] or "").strip(),
            "description": C.trim(row["description"], 300),
            "type": row["type_name"],
            "handle": norm_handle(row["link"]),
            "is_supplementary": bool(row["is_supplementary"]),
        })

    for row in con.execute(
        f"""select d.results_id, d.short_title, d.readiness_level, d.innovation_developers,
                   d.is_new_variety, d.number_of_varieties, irl.name as readiness_name, irl.level
            from results_innovations_dev d
            left join clarisa_innovation_readiness_level irl
                   on irl.id = d.innovation_readiness_level_id
            where d.results_id in ({ph}) and d.is_active = 1""", ids):
        index[row["results_id"]]["innovation"] = {
            "short_title": C.trim(row["short_title"], 300),
            "readiness_level": row["readiness_name"] or row["readiness_level"],
            "readiness_score": row["level"],
            "is_new_variety": bool(row["is_new_variety"]),
            "number_of_varieties": row["number_of_varieties"],
            "developers": C.trim(row["innovation_developers"], 500),
        }

    for row in con.execute(
        f"""select rtr.results_id, rtri.toc_results_indicator_id
            from results_toc_result rtr
            join results_toc_result_indicators rtri
                 on rtri.results_toc_results_id = rtr.result_toc_result_id
            where rtr.results_id in ({ph}) and rtr.is_active = 1""", ids):
        index[row["results_id"]]["toc_indicator_uuids"].append(row["toc_results_indicator_id"])

    for row in con.execute(
        f"""select rbi.result_id, ci.id as initiative_id, ci.official_code, ci.name,
                   rbi.initiative_role_id
            from results_by_inititiative rbi
            join clarisa_initiatives ci on ci.id = rbi.inititiative_id
            where rbi.result_id in ({ph}) and rbi.is_active = 1""", ids):
        index[row["result_id"]]["initiatives"].append({
            "initiative_id": row["initiative_id"],
            "code": (row["official_code"] or "").strip(),
            "name": (row["name"] or "").replace("\xa0", " ").strip(),
            "role_id": row["initiative_role_id"],
        })

    # impact-area targets (empty for 2025 in this snapshot — kept for the live process)
    for row in con.execute(
        f"""select rtr.results_id, ia.name as impact_area
            from result_toc_impact_area_target t
            join results_toc_result rtr on rtr.result_toc_result_id = t.result_toc_result_id
            left join clarisa_impact_area_indicator iai on iai.id = t.impact_area_indicator_id
            left join clarisa_impact_areas ia on ia.id = iai.impact_area_id
            where rtr.results_id in ({ph})""", ids):
        index[row["results_id"]].setdefault("impact_area_targets", []).append(row["impact_area"])


# --------------------------------------------------------------------------------------
# Heuristic result -> HLO mapping
# --------------------------------------------------------------------------------------
def load_hlo_map(porb_extract: str | None) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """(PORB centre, KPI type) -> HLOs, from the PORB extract produced by ``ingest.porb``."""
    if not porb_extract or not Path(porb_extract).exists():
        return {}
    import json
    data = json.loads(Path(porb_extract).read_text(encoding="utf-8"))
    idx: dict[tuple[str, str], Counter] = defaultdict(Counter)
    titles = {h["id"]: h for h in data.get("hlos", [])}
    for ind in data.get("indicators", []):
        if ind.get("center") and ind.get("kpi_type") and ind.get("hlo_id"):
            idx[(ind["center"], ind["kpi_type"])][ind["hlo_id"]] += 1
    out: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for key, counter in idx.items():
        out[key] = [
            {"hlo_id": hid, "rows": n, "label": titles.get(hid, {}).get("label", hid)}
            for hid, n in counter.most_common(3)
        ]
    return out


# --------------------------------------------------------------------------------------
# Claim emission
# --------------------------------------------------------------------------------------
def build_claims(programs: list[dict[str, Any]], results: list[dict[str, Any]],
                 snapshot: str, hlo_map: dict[tuple[str, str], list[dict[str, Any]]],
                 program_code: str) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    seen_objects: set[str] = set()

    def obj(*args, **kwargs) -> str | None:
        claim = C.object_claim(*args, channel=CHANNEL, system=SYSTEM, snapshot=snapshot, **kwargs)
        oid = claim["payload"]["id"]
        if oid in seen_objects:
            return oid
        seen_objects.add(oid)
        claims.append(claim)
        return oid

    def link(subject: str, predicate: str, target: str, ref: str, **kwargs) -> None:
        claims.append(C.link_claim(subject, predicate, target, channel=CHANNEL, system=SYSTEM,
                                   ref=ref, snapshot=snapshot, **kwargs))

    # --- 13 programs (the portfolio spine) --------------------------------------------
    prog_ids: dict[str, str] = {}
    for p in programs:
        pid = C.make_id("program", p["code"].lower())
        prog_ids[p["code"]] = pid
        prog_ids[str(p["initiative_id"])] = pid
        obj("program", pid, p["name"],
            ref=f"clarisa_initiatives.id={p['initiative_id']}",
            description=f"CGIAR Science Program / Accelerator {p['code']} — {p['name']}.",
            attrs={"code": p["code"], "portfolio": "CGIAR 2025-2030",
                   "is_focus_program": p["code"] == program_code},
            alt_ids=[{"scheme": "clarisa_initiative_code", "value": p["code"]},
                     {"scheme": "prms_initiative_id", "value": str(p["initiative_id"])}])

    def country_obj(c: dict[str, Any]) -> str:
        cid = C.make_id("country", c["iso2"].lower())
        obj("country", cid, c["name"], ref=f"clarisa_countries.id={c['clarisa_id']}",
            attrs={"iso2": c["iso2"], "iso3": c["iso3"], "region": None},
            alt_ids=[{"scheme": "iso2", "value": c["iso2"]}] +
                    ([{"scheme": "iso3", "value": c["iso3"]}] if c["iso3"] else []))
        return cid

    def institution_obj(i: dict[str, Any]) -> str:
        iid = C.make_id("institution", f"clarisa-{i['clarisa_id']}")
        obj("institution", iid, i["name"], ref=f"clarisa_institutions.id={i['clarisa_id']}",
            attrs={"acronym": i.get("acronym"), "institution_type": i.get("type"),
                   "hq_country_iso2": i.get("hq_country_iso2"),
                   "is_cgiar_centre": bool(i.get("center_code")) or i.get("type_code") == 54,
                   "center_code": i.get("center_code"), "matched": True},
            alt_ids=[{"scheme": "clarisa_institution_id", "value": str(i["clarisa_id"])}])
        return iid

    for r in results:
        rid = C.make_id("result", f"prms-{r['id']}")
        lead_centre = next((c for c in r["centres"] if c["is_primary"]),
                           r["centres"][0] if r["centres"] else None)
        attrs = {
            "result_type": r["result_type"],
            "result_code": r["result_code"],
            "year": 2025,
            "status": "Quality Assessed",
            "reporting_cycle": "Reporting 2025",
            "gender_tag_level": TAG_LEVELS.get(r["gender_tag_level_id"]),
            "climate_tag_level": TAG_LEVELS.get(r["climate_change_tag_level_id"]),
            "nutrition_tag_level": TAG_LEVELS.get(r["nutrition_tag_level_id"]),
            "environment_tag_level": TAG_LEVELS.get(r["environmental_biodiversity_tag_level_id"]),
            "poverty_tag_level": TAG_LEVELS.get(r["poverty_tag_level_id"]),
            "lead_centre": lead_centre["acronym"] if lead_centre else None,
            "is_krs": bool(r["is_krs"]),
            "krs_url": r["krs_url"],
            "n_partners": len(r["institutions"]),
            "n_countries": len(r["countries"]),
            "n_evidence": len(r["evidence"]),
            "program_code": program_code,
        }
        evidence = [{"kind": "url", "value": e["link"]} for e in r["evidence"][:3]]
        obj("result", rid, r["title"], ref=f"result.id={r['id']}", description=r["description"],
            attrs=attrs, evidence=evidence,
            alt_ids=[{"scheme": "prms_result_id", "value": str(r["id"])}] +
                    ([{"scheme": "prms_result_code", "value": str(r["result_code"])}]
                     if r["result_code"] else []))

        # REPORTED_UNDER: result -> program (every initiative the result is reported under)
        for init in r["initiatives"]:
            pid = prog_ids.get(init["code"]) or prog_ids.get(str(init["initiative_id"]))
            if pid:
                link(rid, "REPORTED_UNDER", pid,
                     f"results_by_inititiative.result_id={r['id']}",
                     attrs={"role_id": init["role_id"], "primary": init["code"] == program_code})

        # PRODUCED_BY: result -> CGIAR centre(s); WITH_PARTNER: everyone else
        for c in r["centres"]:
            iid = institution_obj({**c, "type": "CGIAR Center", "type_code": 54})
            link(rid, "PRODUCED_BY", iid, f"results_center.result_id={r['id']}",
                 attrs={"is_primary": c["is_primary"], "is_leading": c["is_leading"],
                        "center_code": c["center_code"]})
        centre_ids = {c["clarisa_id"] for c in r["centres"]}
        for i in r["institutions"]:
            iid = institution_obj(i)
            if i["clarisa_id"] in centre_ids:
                continue
            predicate = "PRODUCED_BY" if (i["is_leading"] and i["type_code"] == 54) else "WITH_PARTNER"
            link(rid, predicate, iid, f"results_by_institution.result_id={r['id']}",
                 attrs={"role": i["role"], "is_leading": i["is_leading"]})

        # LOCATED_IN: countries and regions
        for c in r["countries"]:
            link(rid, "LOCATED_IN", country_obj(c), f"result_country.result_id={r['id']}",
                 attrs={"kind": "country"})
        for g in r["regions"]:
            gid = C.make_id("region", f"um49-{g['um49']}")
            obj("region", gid, g["name"], ref=f"clarisa_regions.um49Code={g['um49']}",
                attrs={"um49": g["um49"]},
                alt_ids=[{"scheme": "um49", "value": str(g["um49"])}])
            link(rid, "LOCATED_IN", gid, f"result_region.result_id={r['id']}",
                 attrs={"kind": "region"})

        # SAME_AS: the PRMS <-> CGSpace bridge, plus the kp object stub
        kp_handle = norm_handle(r.get("kp_handle"))
        if kp_handle:
            kid = handle_id(kp_handle)
            obj("kp", kid, r["title"], ref=f"results_knowledge_product.handle={kp_handle}",
                description=r["description"],
                attrs={"handle": kp_handle, "doi": r.get("kp_doi"),
                       "kp_type": r.get("kp_type"), "licence": r.get("kp_licence"),
                       "fair": {"findable": r.get("findable"), "accessible": r.get("accesible"),
                                "interoperable": r.get("interoperable"), "reusable": r.get("reusable")},
                       "uri": f"https://hdl.handle.net/{kp_handle}", "from_prms": True},
                alt_ids=[{"scheme": "cgspace_handle", "value": kp_handle}] +
                        ([{"scheme": "doi", "value": str(r["kp_doi"])}] if r.get("kp_doi") else []),
                evidence=[{"kind": "handle", "value": kp_handle}])
            link(rid, "SAME_AS", kid, f"results_knowledge_product.results_id={r['id']}",
                 attrs={"bridge": "prms_handle==cgspace_handle"}, band="high",
                 evidence=[{"kind": "handle", "value": kp_handle}])

        # EVIDENCED_BY: kp when the link is a CGSpace handle, else a document object
        for e in r["evidence"]:
            if e["handle"]:
                tid = handle_id(e["handle"])
                obj("kp", tid, e["description"] or f"CGSpace item {e['handle']}",
                    ref=f"evidence.link={e['link']}",
                    attrs={"handle": e["handle"], "uri": f"https://hdl.handle.net/{e['handle']}",
                           "from_prms_evidence": True},
                    alt_ids=[{"scheme": "cgspace_handle", "value": e["handle"]}])
                link(rid, "EVIDENCED_BY", tid, f"evidence.result_id={r['id']}",
                     attrs={"evidence_type": e["type"], "supplementary": e["is_supplementary"]},
                     evidence=[{"kind": "handle", "value": e["handle"]}], band="high")
            else:
                did = C.make_id("document", "url-" + C.sha1_12(e["link"]))
                obj("document", did, e["description"] or e["link"][:120],
                    ref=f"evidence.link={e['link']}",
                    attrs={"url": e["link"], "evidence_type": e["type"]},
                    alt_ids=[{"scheme": "url", "value": e["link"]}])
                link(rid, "EVIDENCED_BY", did, f"evidence.result_id={r['id']}",
                     attrs={"evidence_type": e["type"], "supplementary": e["is_supplementary"]},
                     evidence=[{"kind": "url", "value": e["link"]}], band="high")

        # innovation objects (Innovation development results)
        if r.get("innovation"):
            inn = r["innovation"]
            iid = C.make_id("innovation", f"prms-{r['id']}")
            obj("innovation", iid, inn["short_title"] or r["title"],
                ref=f"results_innovations_dev.results_id={r['id']}",
                description=C.trim(inn.get("developers"), 1000),
                attrs={"readiness_level": inn.get("readiness_level"),
                       "readiness_score": inn.get("readiness_score"),
                       "is_new_variety": inn.get("is_new_variety"),
                       "number_of_varieties": inn.get("number_of_varieties"),
                       "result_type": r["result_type"]},
                alt_ids=[{"scheme": "prms_result_id", "value": str(r["id"])}])
            # Direction decided by WP-D: the innovation record DESCRIBES the reported result.
            link(iid, "DESCRIBES", rid, f"results_innovations_dev.results_id={r['id']}",
                 attrs={"note": "innovation detail record of the PRMS result"}, band="high")

        # CONTRIBUTES_TO: heuristic result -> HLO (no structured 2025 ToC in the snapshot)
        centre_acr = attrs["lead_centre"]
        kpi = KPI_OF_RESULT_TYPE.get(r["result_type"], "custom")
        for cand in hlo_map.get((centre_acr, kpi), [])[:2]:
            link(rid, "CONTRIBUTES_TO", cand["hlo_id"],
                 f"heuristic:centre={centre_acr};kpi={kpi}",
                 attrs={"mapping": "heuristic", "rule": "lead centre + KPI type -> PORB HLO",
                        "porb_rows": cand["rows"], "centre": centre_acr, "kpi_type": kpi},
                 band="medium",
                 note="No structured 2025 result->ToC mapping exists in the PRMS snapshot.",
                 disambiguator="heuristic")
        if r["toc_indicator_uuids"]:
            claims.append(C.attr_claim(
                rid, {"toc_indicator_refs": sorted(set(r["toc_indicator_uuids"]))[:10],
                      "toc_mapping_status": "unresolved_external_uuid"},
                channel=CHANNEL, system=SYSTEM,
                ref=f"results_toc_result_indicators.results_id={r['id']}", snapshot=snapshot,
                band="medium",
                note="ToC indicator ids reference the external ToC system, not this snapshot."))
        if r.get("impact_area_targets"):
            claims.append(C.attr_claim(
                rid, {"impact_area_targets": sorted({t for t in r["impact_area_targets"] if t})},
                channel=CHANNEL, system=SYSTEM,
                ref=f"result_toc_impact_area_target.results_id={r['id']}", snapshot=snapshot))

    return C.dedupe_links(C.dedupe_objects(claims))


# --------------------------------------------------------------------------------------
def run(db: str, program_code: str, limit: int, out: str, extract: str,
        registry: str = DEFAULT_REGISTRY, porb_extract: str | None = None) -> dict[str, Any]:
    snapshot = Path(db).stem
    con = connect_ro(db)
    try:
        programs = fetch_programs(con)
        focus = next((p for p in programs if p["code"] == program_code), None)
        if focus is None:
            raise SystemExit(f"program {program_code} not found among SP01-SP13")
        cands = candidate_results(con, focus["initiative_id"])
        chosen, stats = select_results(cands, limit, registry_handles(registry))
        enrich(con, chosen)
    finally:
        con.close()

    hlo_map = load_hlo_map(porb_extract)
    claims = build_claims(programs, chosen, snapshot, hlo_map, program_code)

    C.write_extract(extract, {
        "channel": CHANNEL,
        "snapshot": snapshot,
        "source_file": db,
        "program": {"code": program_code, "name": focus["name"],
                    "initiative_id": focus["initiative_id"]},
        "generated_at": C.now_iso(),
        "public": True,
        "selection": stats,
        "hlo_heuristic_available": bool(hlo_map),
        "programs": programs,
        "results": chosen,
    })
    n = C.write_batch(out, claims)
    summary = C.summarise(claims)
    summary.update(channel=CHANNEL, out=out, extract=extract, claims=n, selection=stats)
    return summary


def run_channel(limit: int | None = None, load: bool = True, out: str | None = None,
                program: str = "SP01", db: str | None = None, **_: object) -> dict:
    """Keyword-only entry point for POST /api/ingest/prms (PLAN §4)."""
    out_path = C.channel_out_path(CHANNEL, out)
    return C.channel_entry(CHANNEL, lambda: run(
        db or DEFAULT_DB, program, int(limit or 50), out_path,
        C.runtime_extract_path(CHANNEL), DEFAULT_REGISTRY, "data/seed/porb_sp01.json"), load=load)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="TRACE intake channel: PRMS")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--program", default="SP01")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--out", default="data/claims/seed-prms.jsonl")
    ap.add_argument("--extract", default="data/seed/prms_sp01_results.json")
    ap.add_argument("--registry", default=DEFAULT_REGISTRY)
    ap.add_argument("--porb-extract", default="data/seed/porb_sp01.json")
    a = ap.parse_args(argv)
    s = run(a.db, a.program, a.limit, a.out, a.extract, a.registry, a.porb_extract)
    print(f"[prms] {s['claims']} claims -> {s['out']}")
    print(f"       objects: {s['objects']}")
    print(f"       links:   {s['links']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

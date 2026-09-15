"""Deterministic QA / reconciliation engine (PLAN §3.5). No LLM, no network by default."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from typing import Any, Iterable

import yaml
from rapidfuzz import fuzz

from app.config import get_settings
from app.ids import ID_RE, OBJECT_TYPES, is_valid_id, type_of
from app.models import CLAIM_KINDS, CLAIM_SCHEMA, PREDICATES, PROVENANCE

ISO2_RE = re.compile(r"^[A-Za-z]{2}$")


@lru_cache(maxsize=4)
def _rules_cached(path: str, mtime: float) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_rules() -> dict[str, Any]:
    p = get_settings().qa_rules_path
    try:
        return _rules_cached(str(p), p.stat().st_mtime)
    except FileNotFoundError:  # pragma: no cover - defensive
        return {"bands": {"high": 0.85, "medium": 0.6}, "weights": {}}


@dataclass
class QAContext:
    """Everything QA may look at besides the claim itself."""

    batch_ids: set[str] = field(default_factory=set)   # ids created earlier in the same batch
    known_objects: dict[str, dict] | None = None        # optional cache: id -> row dict
    program_countries: set[str] | None = None           # trace:country:* ids known for the program
    use_taxonomy: bool = False                          # allow a network call to MELIAF


def _check(name: str, ok: bool, note: str = "", severity: str = "hard") -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "note": note, "severity": severity}


# --- db helpers (kept tiny so QA can run on a fresh DB) --------------------

def _object_row(object_id: str) -> dict | None:
    from app.db import query_one

    row = query_one("SELECT * FROM objects WHERE id=?", (object_id,))
    return dict(row) if row else None


def _exists(object_id: str, ctx: QAContext) -> bool:
    if not object_id:
        return False
    if object_id in ctx.batch_ids:
        return True
    if ctx.known_objects is not None and object_id in ctx.known_objects:
        return True
    return _object_row(object_id) is not None


def _alt_id_owner(scheme: str, value: str) -> str | None:
    from app.ids import resolve_alt_id

    try:
        return resolve_alt_id(scheme, value)
    except Exception:  # pragma: no cover - DB not ready
        return None


def _fuzzy_duplicate(type_: str, label: str, self_id: str, threshold: int) -> tuple[str, int] | None:
    from app.db import query

    if not label or len(label) < 8:
        return None
    rows = query("SELECT id, label FROM objects WHERE type=? AND id<>? LIMIT 5000", (type_, self_id))
    best: tuple[str, int] | None = None
    for r in rows:
        score = int(fuzz.token_set_ratio(label, r["label"] or ""))
        if score >= threshold and (best is None or score > best[1]):
            best = (r["id"], score)
    return best


def program_countries_for(subject_id: str) -> set[str]:
    """Countries known for the program a result reports under (via its aows/hlos/projects)."""
    from app.db import query

    if not subject_id:
        return set()
    programs = [
        r["object"]
        for r in query(
            "SELECT object FROM links WHERE subject=? AND predicate IN ('REPORTED_UNDER','PART_OF')",
            (subject_id,),
        )
    ]
    if not programs:
        return set()
    out: set[str] = set()
    for prog in programs:
        rows = query(
            """
            SELECT l2.object AS c FROM links l1
              JOIN links l2 ON l2.subject = l1.subject
             WHERE l1.object = ? AND l1.predicate = 'PART_OF' AND l2.predicate = 'LOCATED_IN'
            UNION
            SELECT l3.object AS c FROM links l1
              JOIN links lh ON lh.object = l1.subject AND lh.predicate='PART_OF'
              JOIN links l3 ON l3.subject = lh.subject AND l3.predicate='LOCATED_IN'
             WHERE l1.object = ? AND l1.predicate = 'PART_OF'
            """,
            (prog, prog),
        )
        out.update(r["c"] for r in rows if r["c"])
    return out


# --- individual checks -----------------------------------------------------

def _check_well_formed(claim: dict) -> list[dict]:
    import jsonschema

    checks: list[dict] = []
    try:
        jsonschema.validate(claim, CLAIM_SCHEMA)
        schema_ok, note = True, ""
    except jsonschema.ValidationError as exc:
        schema_ok, note = False, f"schema: {exc.message}"
    kind = claim.get("kind")
    subject = claim.get("subject") or ""
    predicate = claim.get("predicate")
    obj = claim.get("object") or ""
    problems: list[str] = []
    if note:
        problems.append(note)
    if kind not in CLAIM_KINDS:
        problems.append(f"unknown kind {kind!r}")
    if subject and not ID_RE.match(subject) and kind != "candidate_concept":
        problems.append(f"malformed subject id {subject!r}")
    if kind == "assert_object":
        ptype = (claim.get("payload") or {}).get("type")
        if ptype not in OBJECT_TYPES:
            problems.append(f"unknown object type {ptype!r}")
        elif subject and is_valid_id(subject) and type_of(subject) != ptype:
            problems.append(f"id type {type_of(subject)} != payload type {ptype}")
    if kind == "assert_link":
        spec = PREDICATES.get(predicate or "")
        if spec is None:
            problems.append(f"unknown predicate {predicate!r}")
        else:
            if not is_valid_id(obj):
                problems.append(f"malformed object id {obj!r}")
            else:
                st = type_of(subject) if is_valid_id(subject) else None
                ot = type_of(obj)
                if st and "*" not in spec["from"] and st not in spec["from"]:
                    problems.append(f"{predicate} not allowed from type {st}")
                if "*" not in spec["to"] and ot not in spec["to"]:
                    problems.append(f"{predicate} not allowed to type {ot}")
    if kind == "assert_attr" and not isinstance(claim.get("payload"), dict):
        problems.append("assert_attr payload must be an object")
    checks.append(_check("well_formed", not problems, "; ".join(problems)))
    return checks


def _check_id_resolvable(claim: dict, ctx: QAContext) -> dict:
    kind = claim.get("kind")
    subject = claim.get("subject") or ""
    obj = claim.get("object") or ""
    missing = []
    if kind in ("assert_link", "assert_attr", "retract"):
        if subject and not _exists(subject, ctx):
            missing.append(subject)
    if kind == "assert_link" and obj and not _exists(obj, ctx):
        missing.append(obj)
    return _check("id_resolvable", not missing, ("unresolved: " + ", ".join(missing)) if missing else "")


def _check_duplicate(claim: dict, ctx: QAContext, rules: dict) -> dict:
    if claim.get("kind") != "assert_object":
        return _check("duplicate", True, "n/a")
    subject = claim.get("subject") or ""
    payload = claim.get("payload") or {}
    for alt in payload.get("alt_ids") or []:
        scheme, value = alt.get("scheme"), alt.get("value")
        if not scheme or value in (None, ""):
            continue
        owner = _alt_id_owner(scheme, str(value))
        if owner and owner != subject:
            return _check(
                "duplicate",
                False,
                f"alt-id {scheme}={value} already belongs to {owner}; suggest SAME_AS {subject} -> {owner}",
            )
    threshold = int(rules.get("fuzzy_duplicate_threshold", 92))
    hit = _fuzzy_duplicate(payload.get("type", ""), payload.get("label", ""), subject, threshold)
    if hit:
        return _check(
            "duplicate", False,
            f"label {hit[1]}% similar to {hit[0]} - review for SAME_AS", severity="soft",
        )
    return _check("duplicate", True, "")


def _check_taxonomy(claim: dict, ctx: QAContext) -> dict:
    if claim.get("predicate") != "TAGGED_WITH":
        return _check("taxonomy_resolvable", True, "n/a")
    concept = claim.get("object") or ""
    row = _object_row(concept)
    if row is None:
        if concept in ctx.batch_ids:
            return _check("taxonomy_resolvable", True, "created in batch")
        if ctx.use_taxonomy:
            from app.taxonomy_client import get_client

            term_id = concept.rsplit(":", 1)[-1].upper()
            term = get_client().term(term_id)
            if term:
                status = (term.get("status") or "").lower()
                if status == "deprecated":
                    return _check(
                        "taxonomy_resolvable", False,
                        f"term {term_id} deprecated; propose replaced_by={term.get('replaced_by')}",
                    )
                return _check("taxonomy_resolvable", True, "resolved via taxonomy service")
        return _check("taxonomy_resolvable", False, f"concept {concept} unknown")
    attrs = json.loads(row.get("attrs_json") or "{}")
    if (attrs.get("status") or "").lower() == "deprecated":
        return _check(
            "taxonomy_resolvable", False,
            f"concept {concept} deprecated; propose replaced_by={attrs.get('replaced_by')}",
        )
    return _check("taxonomy_resolvable", True, "")


def _check_geo(claim: dict, ctx: QAContext) -> dict:
    if claim.get("predicate") != "LOCATED_IN":
        return _check("plausible_geo", True, "n/a")
    obj = claim.get("object") or ""
    if not is_valid_id(obj):
        return _check("plausible_geo", False, f"malformed geo id {obj!r}")
    t = type_of(obj)
    if t == "region":
        return _check("plausible_geo", True, "region")
    if t != "country":
        return _check("plausible_geo", False, f"LOCATED_IN target is a {t}, not a country/region")
    iso2 = obj.rsplit(":", 1)[-1]
    if not ISO2_RE.match(iso2):
        return _check("plausible_geo", False, f"invalid ISO-3166 alpha-2 {iso2!r}")
    subject = claim.get("subject") or ""
    if not is_valid_id(subject) or type_of(subject) != "result":
        # hlo/project/melia geography *defines* the programme's country list, it is not checked against it
        return _check("plausible_geo", True, "geography of a non-result object - taken as source of truth")
    known = ctx.program_countries
    if known is None:
        known = program_countries_for(subject)
    if not known:
        return _check("plausible_geo", True, "no programme country list available - passed with note")
    if obj not in known:
        return _check(
            "plausible_geo", False,
            f"{iso2.upper()} is not in the programme's PORB countries - needs review",
            severity="soft",
        )
    return _check("plausible_geo", True, "")


def _years_in(claim: dict) -> list[int]:
    years: list[int] = []
    payload = claim.get("payload") or {}
    for holder in (payload.get("attrs") or {}, payload, claim.get("attrs") or {}):
        if not isinstance(holder, dict):
            continue
        for key in ("year", "reporting_year", "issued_year"):
            v = holder.get(key)
            try:
                if v not in (None, ""):
                    years.append(int(str(v)[:4]))
            except (TypeError, ValueError):
                continue
    return years


def _check_time(claim: dict, rules: dict) -> dict:
    lo, hi = (rules.get("year_range") or [2022, 2026])[:2]
    years = _years_in(claim)
    if not years:
        return _check("plausible_time", True, "no year attribute")
    bad = [y for y in years if not (lo <= y <= hi)]
    return _check("plausible_time", not bad, (f"year(s) {bad} outside {lo}-{hi}") if bad else "")


def _check_evidence(claim: dict) -> dict:
    if claim.get("predicate") != "EVIDENCED_BY":
        return _check("evidence_present", True, "n/a")
    ev = claim.get("evidence") or []
    attrs = (claim.get("payload") or {}).get("attrs") or {}
    has_attr_link = any(attrs.get(k) for k in ("url", "link", "handle", "doi"))
    ok = has_attr_link or any(e.get("kind") in ("url", "handle", "doi") and e.get("value") for e in ev)
    return _check("evidence_present", ok, "" if ok else "EVIDENCED_BY without url/handle/doi")


def _check_provenance(claim: dict, rules: dict) -> tuple[dict, float]:
    prov = claim.get("provenance") or "unknown"
    penalties = rules.get("provenance_penalty") or {}
    if prov not in PROVENANCE:
        pen = float(penalties.get("unknown", 0.1))
        return _check("provenance_strength", False, f"unknown provenance {prov!r}"), pen
    pen = float(penalties.get(prov, 0.05))
    note = {"signed": "signed (strongest)", "recorded": "recorded", "harvested": "harvested (weakest)"}[prov]
    return _check("provenance_strength", True, note), pen


# --- entry point -----------------------------------------------------------

def run_qa(claim: dict, ctx: QAContext | None = None) -> dict[str, Any]:
    """Score one claim. Returns {band, score, checks[], status}."""
    ctx = ctx or QAContext()
    rules = load_rules()
    weights = rules.get("weights") or {}
    soft = float(rules.get("soft_factor", 0.6))

    checks: list[dict] = []
    checks.extend(_check_well_formed(claim))
    checks.append(_check_id_resolvable(claim, ctx))
    if claim.get("kind") == "retract":
        # a retraction is judged on its form and its author, never on the plausibility of the
        # statement it removes (that statement is exactly what someone is objecting to)
        checks.append(_check("retraction", True, "content checks not applicable to a retraction"))
    else:
        checks.append(_check_duplicate(claim, ctx, rules))
        checks.append(_check_taxonomy(claim, ctx))
        checks.append(_check_geo(claim, ctx))
        checks.append(_check_time(claim, rules))
        checks.append(_check_evidence(claim))
    prov_check, prov_penalty = _check_provenance(claim, rules)
    checks.append(prov_check)

    score = 1.0
    for c in checks:
        if c["ok"] or c["name"] == "provenance_strength":
            continue  # provenance is scored through provenance_penalty below, not as a flat weight
        w = float(weights.get(c["name"], 0.2))
        if c.get("severity") == "soft":
            w *= soft
        score -= w
    score -= prov_penalty * float(weights.get("provenance_strength", 1.0))
    score = max(0.0, min(1.0, round(score, 4)))

    bands = rules.get("bands") or {}
    high, medium = float(bands.get("high", 0.85)), float(bands.get("medium", 0.6))
    if score >= high:
        band, status = "high", "accepted"
    elif score >= medium:
        band, status = "medium", "review"
    else:
        band, status = "low", "rejected"

    if claim.get("kind") in (rules.get("force_review_kinds") or []) and status == "accepted":
        status = "review"
        checks.append(_check("policy", True, f"kind {claim.get('kind')} always enters the review queue"))

    return {"band": band, "score": score, "checks": checks, "status": status,
            "decided_by": None, "decided_at": None, "at": date.today().isoformat()}


def rerun_all() -> dict[str, int]:
    """Re-score every stored claim with the current rules (used by `qa-rerun`)."""
    from app.db import connect

    counts = {"claims": 0, "changed": 0}
    with connect() as conn:
        rows = list(conn.execute("SELECT * FROM claims ORDER BY seq"))
        for row in rows:
            claim = _row_to_claim(row)
            qa = run_qa(claim)
            counts["claims"] += 1
            if qa["status"] != row["status"] and row["decided_by"] is None:
                counts["changed"] += 1
                conn.execute(
                    "UPDATE claims SET qa_json=?, status=? WHERE id=?",
                    (json.dumps(qa), qa["status"], row["id"]),
                )
            elif row["decided_by"] is None:
                conn.execute("UPDATE claims SET qa_json=? WHERE id=?", (json.dumps(qa), row["id"]))
    return counts


def _row_to_claim(row) -> dict:
    return {
        "id": row["id"], "kind": row["kind"], "subject": row["subject"],
        "predicate": row["predicate"], "object": row["object"],
        "payload": json.loads(row["payload_json"] or "{}"),
        "attested_by": row["attested_by"], "provenance": row["provenance"],
        "signature": row["signature"], "evidence": json.loads(row["evidence_json"] or "[]"),
        "taxonomy_version": row["taxonomy_version"],
        "source": json.loads(row["source_json"] or "{}"),
        "created_at": row["created_at"], "supersedes": row["supersedes"],
    }


def summarise(checks: Iterable[dict]) -> str:
    failed = [c["name"] for c in checks if not c["ok"]]
    return "ok" if not failed else "failed: " + ", ".join(failed)

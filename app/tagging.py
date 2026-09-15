"""Taxonomy tagging: resolve text through the MELIAF service and append TAGGED_WITH claims."""
from __future__ import annotations

from typing import Any

from app.ids import concept_id
from app.objects import get_object
from app.qa import QAContext
from app.registry import append_claim
from app.taxonomy_client import get_client

BAND_BY_VIA = {"pref_label": "high", "alt_label": "medium", "stem": "medium"}


def tag_text(text: str) -> dict[str, Any]:
    res = get_client().resolve(text)
    return {"text": text, "matches": res.get("matches", []), "source": res.get("source"),
            "reachable": res.get("reachable", False)}


def _concept_claim(match: dict, taxonomy_version: str | None) -> dict:
    term_id = str(match.get("term_id") or match.get("id") or "")
    cid = concept_id(term_id)
    payload = {
        "type": "concept",
        "label": match.get("pref_label") or term_id,
        "description": match.get("definition") or "",
        "attrs": {"layer": str(match.get("layer") or ""), "status": match.get("status") or "active",
                  "uri": match.get("uri")},
        "alt_ids": [{"scheme": "taxonomy_term_id", "value": term_id}]
        + ([{"scheme": "taxonomy_uri", "value": match["uri"]}] if match.get("uri") else []),
        "source": {"system": "taxonomy", "ref": term_id, "snapshot": taxonomy_version},
    }
    return {"kind": "assert_object", "subject": cid, "payload": payload,
            "attested_by": "ingest:taxonomy@synapsis", "provenance": "harvested",
            "taxonomy_version": taxonomy_version}


def tag_objects(object_ids: list[str], attested_by: str = "ingest:taxonomy@synapsis") -> dict[str, Any]:
    client = get_client()
    health = client.health()
    taxonomy_version = health.get("version")
    ctx = QAContext()
    out: dict[str, Any] = {"objects": [], "claims": 0, "concepts": 0,
                           "taxonomy": {"reachable": health.get("reachable"), "version": taxonomy_version}}
    for oid in object_ids:
        obj = get_object(oid, with_claims=False)
        if obj is None:
            out["objects"].append({"id": oid, "error": "unknown object"})
            continue
        text = f"{obj.get('label','')}. {obj.get('description','')}"
        matches = client.resolve(text).get("matches") or []
        tagged = []
        for m in matches:
            term_id = str(m.get("term_id") or m.get("id") or "")
            if not term_id:
                continue
            cid = concept_id(term_id)
            if get_object(cid, with_claims=False) is None and cid not in ctx.batch_ids:
                append_claim(_concept_claim(m, taxonomy_version), ctx=ctx)
                out["concepts"] += 1
            band_hint = BAND_BY_VIA.get(str(m.get("via")), "medium")
            claim = {
                "kind": "assert_link", "subject": oid, "predicate": "TAGGED_WITH", "object": cid,
                "payload": {"attrs": {"matched_text": m.get("matched_text"), "via": m.get("via"),
                                      "layer": m.get("layer"), "confidence": m.get("confidence"),
                                      "band_hint": band_hint}},
                "attested_by": attested_by, "provenance": "harvested",
                "taxonomy_version": taxonomy_version,
                "source": {"system": "taxonomy", "ref": term_id},
            }
            stored = append_claim(claim, ctx=ctx)
            out["claims"] += 1
            tagged.append({"concept": cid, "term_id": term_id, "via": m.get("via"),
                           "status": stored.get("status")})
        out["objects"].append({"id": oid, "tags": tagged})
    return out

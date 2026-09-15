"""Object read services: search (FTS), detail with links/claims/tags, stats, resolve-id."""
from __future__ import annotations

import json
import re
from typing import Any

from app.db import connect
from app.ids import resolve_alt_id

_FTS_SAFE = re.compile(r'[^\w\s\-]')


def row_to_object(row) -> dict[str, Any]:
    return {
        "id": row["id"], "type": row["type"], "label": row["label"],
        "description": row["description"],
        "attrs": json.loads(row["attrs_json"] or "{}"),
        "alt_ids": json.loads(row["alt_ids_json"] or "[]"),
        "source": json.loads(row["source_json"] or "{}"),
        "qa": json.loads(row["qa_json"] or "{}"),
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


def fts_query(q: str) -> str:
    """Turn free user text into a safe FTS5 prefix query."""
    tokens = [t for t in _FTS_SAFE.sub(" ", q or "").split() if t]
    return " AND ".join(f'"{t}"*' for t in tokens)


def search_objects(type_: str | None = None, q: str | None = None, limit: int = 50,
                   offset: int = 0, band: str | None = None, source: str | None = None) -> dict:
    where, params = [], []
    join = ""
    if q:
        expr = fts_query(q)
        if expr:
            join = "JOIN objects_fts f ON f.id = o.id"
            where.append("objects_fts MATCH ?")
            params.append(expr)
        else:
            where.append("o.label LIKE ?")
            params.append(f"%{q}%")
    if type_:
        types = [t.strip() for t in type_.split(",") if t.strip()]
        where.append("o.type IN (%s)" % ",".join("?" * len(types)))
        params.extend(types)
    if band:
        where.append("json_extract(o.qa_json,'$.band')=?")
        params.append(band)
    if source:
        where.append("json_extract(o.source_json,'$.system')=?")
        params.append(source)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    order = "ORDER BY rank" if join else "ORDER BY o.type, o.label"
    with connect(readonly=True) as conn:
        total = conn.execute(f"SELECT COUNT(*) c FROM objects o {join} {clause}", params).fetchone()["c"]
        rows = conn.execute(
            f"SELECT o.* FROM objects o {join} {clause} {order} LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    return {"total": total, "items": [row_to_object(r) for r in rows]}


def get_object(object_id: str, with_claims: bool = True) -> dict | None:
    with connect(readonly=True) as conn:
        row = conn.execute("SELECT * FROM objects WHERE id=?", (object_id,)).fetchone()
        if row is None:
            return None
        obj = row_to_object(row)
        out_rows = conn.execute(
            """SELECT l.*, o.label AS n_label, o.type AS n_type FROM links l
                 LEFT JOIN objects o ON o.id = l.object WHERE l.subject=? ORDER BY l.predicate""",
            (object_id,),
        ).fetchall()
        in_rows = conn.execute(
            """SELECT l.*, o.label AS n_label, o.type AS n_type FROM links l
                 LEFT JOIN objects o ON o.id = l.subject WHERE l.object=? ORDER BY l.predicate""",
            (object_id,),
        ).fetchall()
        # CONTRACT (frontend): every link carries a denormalised `neighbour` {id, type, label}
        # for the other end, on top of the flat subject/object/label/type fields.
        obj["links_out"] = [
            {"id": r["id"], "predicate": r["predicate"], "subject": object_id, "object": r["object"],
             "label": r["n_label"] or r["object"], "type": r["n_type"],
             "neighbour": {"id": r["object"], "label": r["n_label"] or r["object"], "type": r["n_type"]},
             "attrs": json.loads(r["attrs_json"] or "{}"), "claim_id": r["claim_id"],
             "qa": json.loads(r["qa_json"] or "{}")}
            for r in out_rows
        ]
        obj["links_in"] = [
            {"id": r["id"], "predicate": r["predicate"], "subject": r["subject"], "object": object_id,
             "label": r["n_label"] or r["subject"], "type": r["n_type"],
             "neighbour": {"id": r["subject"], "label": r["n_label"] or r["subject"], "type": r["n_type"]},
             "attrs": json.loads(r["attrs_json"] or "{}"), "claim_id": r["claim_id"],
             "qa": json.loads(r["qa_json"] or "{}")}
            for r in in_rows
        ]
        obj["tags"] = [
            {"id": l["object"], "label": l["label"], "layer": l["attrs"].get("layer"),
             "via": l["attrs"].get("via"), "confidence": l["attrs"].get("confidence"),
             "matched_text": l["attrs"].get("matched_text"), "predicate": "TAGGED_WITH",
             "attrs": l["attrs"]}
            for l in obj["links_out"] if l["predicate"] == "TAGGED_WITH"
        ]
        if with_claims:
            crows = conn.execute(
                "SELECT * FROM claims WHERE subject=? OR object=? ORDER BY seq", (object_id, object_id)
            ).fetchall()
            from app.registry import _row_to_claim

            obj["claims"] = [_row_to_claim(r) for r in crows]
            obj["claim_count"] = len(obj["claims"])
        else:
            obj["claim_count"] = conn.execute(
                "SELECT COUNT(*) c FROM claims WHERE subject=? OR object=?", (object_id, object_id)
            ).fetchone()["c"]
    return obj


def resolve(scheme: str, value: str) -> dict | None:
    oid = resolve_alt_id(scheme, value)
    if not oid:
        return None
    return get_object(oid, with_claims=False)


def stats() -> dict[str, Any]:
    with connect(readonly=True) as conn:
        by_type = {r["type"]: r["c"] for r in conn.execute(
            "SELECT type, COUNT(*) c FROM objects GROUP BY type ORDER BY c DESC")}
        by_predicate = {r["predicate"]: r["c"] for r in conn.execute(
            "SELECT predicate, COUNT(*) c FROM links GROUP BY predicate ORDER BY c DESC")}
        by_band = {(r["b"] or "unknown"): r["c"] for r in conn.execute(
            "SELECT json_extract(qa_json,'$.band') b, COUNT(*) c FROM claims GROUP BY b")}
        by_status = {r["status"]: r["c"] for r in conn.execute(
            "SELECT status, COUNT(*) c FROM claims GROUP BY status")}
        by_source = {(r["s"] or "unknown"): r["c"] for r in conn.execute(
            "SELECT json_extract(source_json,'$.system') s, COUNT(*) c FROM objects GROUP BY s")}
        by_provenance = {(r["provenance"] or "unknown"): r["c"] for r in conn.execute(
            "SELECT provenance, COUNT(*) c FROM claims GROUP BY provenance")}
        last_ingest = {r["channel"]: {"ran_at": r["ran_at"], "counts": json.loads(r["counts_json"] or "{}")}
                       for r in conn.execute(
                           "SELECT channel, MAX(ran_at) ran_at, counts_json FROM ingest_runs GROUP BY channel")}
        totals = {
            "objects": conn.execute("SELECT COUNT(*) c FROM objects").fetchone()["c"],
            "links": conn.execute("SELECT COUNT(*) c FROM links").fetchone()["c"],
            "claims": conn.execute("SELECT COUNT(*) c FROM claims").fetchone()["c"],
            "review_queue": conn.execute(
                "SELECT COUNT(*) c FROM claims WHERE status='review'").fetchone()["c"],
        }
        versions = [dict(r) for r in conn.execute(
            "SELECT version, created_at FROM versions ORDER BY created_at DESC LIMIT 5")]
    return {
        "totals": totals, "objects_by_type": by_type, "links_by_predicate": by_predicate,
        "claims_by_band": by_band, "claims_by_status": by_status,
        "claims_by_provenance": by_provenance, "objects_by_source": by_source,
        # aliases for the SPA contract (same numbers, shorter names)
        "qa_bands": by_band, "by_source": by_source,
        "last_ingest": last_ingest, "recent_versions": versions,
    }


def record_ingest(channel: str, counts: dict) -> None:
    from app.registry import now_iso

    with connect() as conn:
        conn.execute("INSERT INTO ingest_runs(channel, ran_at, counts_json) VALUES(?,?,?)",
                     (channel, now_iso(), json.dumps(counts)))

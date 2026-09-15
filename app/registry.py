"""Append-only claims registry + materialisation into the object/link graph (PLAN §3.4)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ulid import ULID

from app.db import connect
from app.ids import normalise_alt_id
from app.models import ClaimIn
from app.qa import QAContext, run_qa

MATERIALISING_KINDS = ("assert_object", "assert_attr", "assert_link", "retract")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_claim_id() -> str:
    return f"clm_{ULID()}"


def new_link_id() -> str:
    return f"lnk_{ULID()}"


class RegistryError(ValueError):
    pass


# --------------------------------------------------------------------------- read

def _row_to_claim(row) -> dict[str, Any]:
    qa = json.loads(row["qa_json"] or "{}")
    return {
        "id": row["id"], "kind": row["kind"], "subject": row["subject"],
        "predicate": row["predicate"], "object": row["object"],
        "payload": json.loads(row["payload_json"] or "{}"),
        "attested_by": row["attested_by"], "provenance": row["provenance"],
        "signature": row["signature"], "evidence": json.loads(row["evidence_json"] or "[]"),
        "taxonomy_version": row["taxonomy_version"],
        "source": json.loads(row["source_json"] or "{}"),
        "created_at": row["created_at"], "supersedes": row["supersedes"],
        "status": row["status"], "decided_by": row["decided_by"], "decided_at": row["decided_at"],
        "qa": qa,
    }


def get_claim(claim_id: str) -> dict | None:
    with connect(readonly=True) as conn:
        row = conn.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone()
        if not row:
            return None
        claim = _row_to_claim(row)
        chain: list[str] = []
        cur = claim.get("supersedes")
        seen = set()
        while cur and cur not in seen:
            seen.add(cur)
            chain.append(cur)
            nxt = conn.execute("SELECT supersedes FROM claims WHERE id=?", (cur,)).fetchone()
            cur = nxt["supersedes"] if nxt else None
        sup_by = conn.execute("SELECT id FROM claims WHERE supersedes=?", (claim_id,)).fetchall()
        claim["supersede_chain"] = chain
        claim["superseded_by"] = [r["id"] for r in sup_by]
    return claim


def list_claims(status: str | None = None, band: str | None = None, subject: str | None = None,
                kind: str | None = None, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    where, params = [], []
    if status:
        where.append("status=?")
        params.append(status)
    if subject:
        where.append("subject=?")
        params.append(subject)
    if kind:
        where.append("kind=?")
        params.append(kind)
    if band:
        where.append("json_extract(qa_json,'$.band')=?")
        params.append(band)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    with connect(readonly=True) as conn:
        total = conn.execute(f"SELECT COUNT(*) c FROM claims {clause}", params).fetchone()["c"]
        rows = conn.execute(
            f"SELECT * FROM claims {clause} ORDER BY seq DESC LIMIT ? OFFSET ?", [*params, limit, offset]
        ).fetchall()
    return {"total": total, "items": [_row_to_claim(r) for r in rows]}


# --------------------------------------------------------------------------- materialise

def _merge_alt_ids(conn, object_id: str, alt_ids: Iterable[dict]) -> list[dict]:
    existing_row = conn.execute("SELECT alt_ids_json FROM objects WHERE id=?", (object_id,)).fetchone()
    existing = json.loads(existing_row["alt_ids_json"]) if existing_row else []
    merged = {(a["scheme"], str(a["value"])): a for a in existing if a.get("scheme")}
    for a in alt_ids or []:
        if not a.get("scheme") or a.get("value") in (None, ""):
            continue
        scheme, value = normalise_alt_id(a["scheme"], str(a["value"]))
        merged[(scheme, value)] = {"scheme": scheme, "value": value}
        conn.execute(
            "INSERT INTO alt_ids(scheme, value, object_id) VALUES(?,?,?) "
            "ON CONFLICT(scheme, value) DO UPDATE SET object_id=excluded.object_id",
            (scheme, value, object_id),
        )
    return list(merged.values())


def _fts_upsert(conn, object_id: str, label: str, description: str) -> None:
    conn.execute("DELETE FROM objects_fts WHERE id=?", (object_id,))
    conn.execute(
        "INSERT INTO objects_fts(id, label, description) VALUES(?,?,?)",
        (object_id, label or "", description or ""),
    )


def _upsert_object(conn, claim: dict) -> None:
    oid = claim["subject"]
    payload = claim.get("payload") or {}
    ts = claim.get("created_at") or now_iso()
    row = conn.execute("SELECT * FROM objects WHERE id=?", (oid,)).fetchone()
    attrs = json.loads(row["attrs_json"]) if row else {}
    attrs.update({k: v for k, v in (payload.get("attrs") or {}).items()})
    label = payload.get("label") or (row["label"] if row else "")
    description = payload.get("description") or (row["description"] if row else "")
    source = payload.get("source") or (json.loads(row["source_json"]) if row else {})
    qa = claim.get("qa") or {}
    qa_min = {"band": qa.get("band"), "score": qa.get("score")}
    alt_ids = _merge_alt_ids(conn, oid, payload.get("alt_ids") or [])
    if row:
        conn.execute(
            "UPDATE objects SET type=?, label=?, description=?, attrs_json=?, alt_ids_json=?, "
            "source_json=?, qa_json=?, updated_at=? WHERE id=?",
            (payload.get("type") or row["type"], label, description, json.dumps(attrs),
             json.dumps(alt_ids), json.dumps(source), json.dumps(qa_min), ts, oid),
        )
    else:
        conn.execute(
            "INSERT INTO objects(id, type, label, description, attrs_json, alt_ids_json, source_json, "
            "qa_json, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (oid, payload.get("type"), label, description, json.dumps(attrs), json.dumps(alt_ids),
             json.dumps(source), json.dumps(qa_min), ts, ts),
        )
    _fts_upsert(conn, oid, label, description)


def _merge_attr(conn, claim: dict) -> None:
    oid = claim["subject"]
    payload = claim.get("payload") or {}
    body = payload.get("attrs") if isinstance(payload.get("attrs"), dict) else {
        k: v for k, v in payload.items() if k not in ("type", "label", "description", "alt_ids", "source")
    }
    row = conn.execute("SELECT * FROM objects WHERE id=?", (oid,)).fetchone()
    if row is None:
        # attr about an unknown object: create a stub so nothing is lost
        conn.execute(
            "INSERT INTO objects(id, type, label, description, attrs_json, alt_ids_json, source_json, "
            "qa_json, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (oid, oid.split(":")[1], payload.get("label", ""), "", json.dumps(body), "[]", "{}",
             json.dumps({"band": (claim.get("qa") or {}).get("band")}), now_iso(), now_iso()),
        )
        _fts_upsert(conn, oid, payload.get("label", ""), "")
        return
    attrs = json.loads(row["attrs_json"] or "{}")
    attrs.update(body)
    label = payload.get("label") or row["label"]
    description = payload.get("description") or row["description"]
    conn.execute(
        "UPDATE objects SET attrs_json=?, label=?, description=?, updated_at=? WHERE id=?",
        (json.dumps(attrs), label, description, claim.get("created_at") or now_iso(), oid),
    )
    if payload.get("alt_ids"):
        alt = _merge_alt_ids(conn, oid, payload["alt_ids"])
        conn.execute("UPDATE objects SET alt_ids_json=? WHERE id=?", (json.dumps(alt), oid))
    _fts_upsert(conn, oid, label, description)


def _insert_link(conn, claim: dict) -> None:
    payload = claim.get("payload") or {}
    attrs = payload.get("attrs") if isinstance(payload.get("attrs"), dict) else {}
    qa = claim.get("qa") or {}
    existing = conn.execute(
        "SELECT id FROM links WHERE subject=? AND predicate=? AND object=?",
        (claim["subject"], claim["predicate"], claim["object"]),
    ).fetchone()
    lid = existing["id"] if existing else new_link_id()
    conn.execute(
        "INSERT INTO links(id, subject, predicate, object, attrs_json, claim_id, qa_json) "
        "VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET attrs_json=excluded.attrs_json, "
        "claim_id=excluded.claim_id, qa_json=excluded.qa_json",
        (lid, claim["subject"], claim["predicate"], claim["object"], json.dumps(attrs),
         claim.get("id"), json.dumps({"band": qa.get("band"), "score": qa.get("score")})),
    )


def _retract(conn, claim: dict) -> None:
    """Retract a link (subject+predicate+object), a whole object, or a previous claim's effect."""
    payload = claim.get("payload") or {}
    target_claim = payload.get("claim_id") or claim.get("supersedes")
    if claim.get("predicate") and claim.get("object"):
        conn.execute(
            "DELETE FROM links WHERE subject=? AND predicate=? AND object=?",
            (claim["subject"], claim["predicate"], claim["object"]),
        )
        return
    if target_claim:
        conn.execute("DELETE FROM links WHERE claim_id=?", (target_claim,))
        return
    oid = claim.get("subject")
    conn.execute("DELETE FROM links WHERE subject=? OR object=?", (oid, oid))
    conn.execute("DELETE FROM alt_ids WHERE object_id=?", (oid,))
    conn.execute("DELETE FROM objects_fts WHERE id=?", (oid,))
    conn.execute("DELETE FROM objects WHERE id=?", (oid,))


def materialise(conn, claim: dict) -> None:
    kind = claim.get("kind")
    if kind == "assert_object":
        _upsert_object(conn, claim)
    elif kind == "assert_attr":
        _merge_attr(conn, claim)
    elif kind == "assert_link":
        _insert_link(conn, claim)
    elif kind == "retract":
        _retract(conn, claim)
    # candidate_concept claims never materialise: they feed the review queue / coverage map.


# --------------------------------------------------------------------------- append

def _normalise(claim_in: dict | ClaimIn) -> dict[str, Any]:
    if isinstance(claim_in, ClaimIn):
        claim = claim_in.model_dump()
    else:
        claim = dict(claim_in)
    claim.setdefault("payload", {})
    claim.setdefault("evidence", [])
    claim.setdefault("source", {})
    claim.setdefault("provenance", "recorded")
    claim.setdefault("attested_by", "agent:anonymous")
    claim.setdefault("supersedes", None)
    claim["created_at"] = claim.get("created_at") or now_iso()
    claim["id"] = claim.get("id") or new_claim_id()
    return claim


def append_claim(claim_in: dict | ClaimIn, dry_run: bool = False, ctx: QAContext | None = None,
                 sign_with: str | None = None) -> dict[str, Any]:
    """Validate → QA → store → materialise (when accepted). Returns the stored claim."""
    claim = _normalise(claim_in)
    if sign_with:
        from app.signing import sign

        claim["provenance"] = "signed"
        claim["signature"] = sign(claim, sign_with)
    qa = run_qa(claim, ctx)
    claim["qa"] = qa
    claim["status"] = qa["status"]
    claim["decided_by"] = None
    claim["decided_at"] = None
    if dry_run:
        claim["dry_run"] = True
        claim["materialised"] = False
        return claim

    with connect() as conn:
        already = conn.execute("SELECT 1 FROM claims WHERE id=?", (claim["id"],)).fetchone()
        if already:
            # re-loading a batch with explicit claim ids is a no-op, never an error
            existing = _row_to_claim(conn.execute("SELECT * FROM claims WHERE id=?", (claim["id"],)).fetchone())
            existing["already_present"] = True
            existing["materialised"] = existing.get("status") == "accepted"
            return existing
        conn.execute(
            """INSERT INTO claims(id, kind, subject, predicate, object, payload_json, attested_by,
                provenance, signature, evidence_json, taxonomy_version, source_json, created_at,
                supersedes, qa_json, status, decided_by, decided_at, seq)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                      (SELECT COALESCE(MAX(seq),0)+1 FROM claims))""",
            (claim["id"], claim["kind"], claim.get("subject"), claim.get("predicate"),
             claim.get("object"), json.dumps(claim.get("payload") or {}), claim.get("attested_by"),
             claim.get("provenance"), claim.get("signature"), json.dumps(claim.get("evidence") or []),
             claim.get("taxonomy_version"), json.dumps(claim.get("source") or {}),
             claim["created_at"], claim.get("supersedes"), json.dumps(qa), qa["status"], None, None),
        )
        if claim.get("supersedes"):
            # the superseded claim stays in the log but stops materialising
            conn.execute(
                "UPDATE claims SET status='superseded' WHERE id=? AND status<>'superseded'",
                (claim["supersedes"],),
            )
        if qa["status"] == "accepted":
            materialise(conn, claim)
    if claim.get("supersedes"):
        # a correction may remove what the old claim asserted -> cheapest correct answer is a replay
        rebuild()
        refreshed = get_claim(claim["id"])
        if refreshed:
            claim = refreshed
    claim["materialised"] = claim.get("status") == "accepted"
    if ctx is not None and claim["kind"] == "assert_object" and claim["status"] == "accepted":
        ctx.batch_ids.add(claim["subject"])
    return claim


def decide(claim_id: str, decision: str, by: str = "person:unknown", note: str = "") -> dict[str, Any]:
    """Human review decision. Decisions are recorded on the claim and the graph is re-materialised."""
    if decision not in ("accept", "reject"):
        raise RegistryError("decision must be accept or reject")
    status = "accepted" if decision == "accept" else "rejected"
    with connect() as conn:
        row = conn.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone()
        if row is None:
            raise RegistryError(f"unknown claim {claim_id}")
        qa = json.loads(row["qa_json"] or "{}")
        qa["status"] = status
        qa["decided_by"] = by
        qa["decided_at"] = now_iso()
        qa.setdefault("checks", []).append(
            {"name": "human_review", "ok": decision == "accept", "note": note or decision}
        )
        conn.execute(
            "UPDATE claims SET status=?, qa_json=?, decided_by=?, decided_at=? WHERE id=?",
            (status, json.dumps(qa), by, qa["decided_at"], claim_id),
        )
    rebuild()
    return get_claim(claim_id) or {}


def rebuild() -> dict[str, int]:
    """Replay the whole claims log into fresh object/link tables. Idempotent."""
    with connect() as conn:
        superseded = {
            r["supersedes"]
            for r in conn.execute(
                "SELECT supersedes FROM claims WHERE supersedes IS NOT NULL AND status='accepted'"
            )
        }
        conn.execute("DELETE FROM links")
        conn.execute("DELETE FROM alt_ids")
        conn.execute("DELETE FROM objects_fts")
        conn.execute("DELETE FROM objects")
        rows = list(conn.execute("SELECT * FROM claims WHERE status='accepted' ORDER BY seq"))
        applied = 0
        for row in rows:
            if row["id"] in superseded:
                continue
            claim = _row_to_claim(row)
            materialise(conn, claim)
            applied += 1
        objects = conn.execute("SELECT COUNT(*) c FROM objects").fetchone()["c"]
        links = conn.execute("SELECT COUNT(*) c FROM links").fetchone()["c"]
    return {"claims_replayed": applied, "objects": objects, "links": links}


def prescan_ids(paths: Iterable[str | Path]) -> set[str]:
    """Ids that will exist once these batches are loaded (PLAN §3.5 'created in the same batch')."""
    ids: set[str] = set()
    for path in paths:
        p = Path(path)
        if not p.exists():
            continue
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line.startswith("{") or '"assert_object"' not in line:
                    continue
                try:
                    claim = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if claim.get("kind") == "assert_object" and claim.get("subject"):
                    ids.add(claim["subject"])
    return ids


def load_batches(paths: list[str | Path], dry_run: bool = False) -> list[dict[str, Any]]:
    """Load several batches as one logical batch: ids created in any of them resolve in all."""
    ctx = QAContext(batch_ids=prescan_ids(paths))
    return [load_batch(p, dry_run=dry_run, ctx=ctx) for p in paths]


def load_batch(path: str | Path, dry_run: bool = False, ctx: QAContext | None = None) -> dict[str, Any]:
    """Append every claim in a jsonl batch, sharing one QA context (batch-local ids resolve)."""
    p = Path(path)
    ctx = ctx if ctx is not None else QAContext(batch_ids=prescan_ids([p]))
    summary = {"file": str(p), "claims": 0, "accepted": 0, "review": 0, "rejected": 0, "errors": []}
    with p.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                claim = json.loads(line)
            except json.JSONDecodeError as exc:
                summary["errors"].append(f"{p.name}:{lineno}: {exc}")
                continue
            try:
                out = append_claim(claim, dry_run=dry_run, ctx=ctx)
            except Exception as exc:  # keep loading the rest of the batch
                summary["errors"].append(f"{p.name}:{lineno}: {exc}")
                continue
            summary["claims"] += 1
            summary[out.get("status", "review")] = summary.get(out.get("status", "review"), 0) + 1
    return summary


def counts() -> dict[str, int]:
    with connect(readonly=True) as conn:
        return {
            "objects": conn.execute("SELECT COUNT(*) c FROM objects").fetchone()["c"],
            "links": conn.execute("SELECT COUNT(*) c FROM links").fetchone()["c"],
            "claims": conn.execute("SELECT COUNT(*) c FROM claims").fetchone()["c"],
        }

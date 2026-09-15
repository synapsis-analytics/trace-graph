"""Lightweight identity/signing layer (PLAN D6): HMAC-SHA256 stand-in for did:web/VC."""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

CANONICAL_FIELDS = ("kind", "subject", "predicate", "object", "payload", "attested_by",
                    "created_at", "supersedes")


def canonical(claim: dict[str, Any]) -> str:
    """Deterministic serialisation of the signable part of a claim."""
    body = {k: claim.get(k) for k in CANONICAL_FIELDS}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sign(claim: dict[str, Any], secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), canonical(claim).encode("utf-8"), hashlib.sha256).hexdigest()


def verify(claim: dict[str, Any], secret: str) -> bool:
    sig = claim.get("signature") or ""
    return bool(sig) and hmac.compare_digest(sig, sign(claim, secret))


def secret_hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def register_agent(agent_id: str, name: str, secret: str, kind: str = "agent") -> dict[str, Any]:
    from app.db import connect

    with connect() as conn:
        conn.execute(
            "INSERT INTO agents(id, name, secret_hash, kind) VALUES(?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, secret_hash=excluded.secret_hash, kind=excluded.kind",
            (agent_id, name, secret_hash(secret), kind),
        )
    return {"id": agent_id, "name": name, "kind": kind}


def known_agent(agent_id: str) -> dict | None:
    from app.db import query_one

    row = query_one("SELECT * FROM agents WHERE id=?", (agent_id,))
    return dict(row) if row else None

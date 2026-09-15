"""/api/claims — the append-only registry surface."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import require_key
from app.models import ClaimIn, DecisionIn
from app.registry import RegistryError, append_claim, decide, get_claim, list_claims

router = APIRouter(prefix="/api", tags=["claims"])


@router.get("/claims")
def claims(
    status: str | None = None,
    band: str | None = None,
    subject: str | None = None,
    kind: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    return list_claims(status=status, band=band, subject=subject, kind=kind, limit=limit, offset=offset)


@router.get("/claims/{claim_id}")
def claim_detail(claim_id: str):
    claim = get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"unknown claim {claim_id}")
    return claim


@router.post("/claims")
def post_claim(claim: ClaimIn, dry_run: int = 0, _key: str = Depends(require_key)):
    return append_claim(claim, dry_run=bool(dry_run))


@router.post("/claims/{claim_id}/decide")
def post_decision(claim_id: str, body: DecisionIn, _key: str = Depends(require_key)):
    try:
        return decide(claim_id, body.decision, by=body.by, note=body.note)
    except RegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

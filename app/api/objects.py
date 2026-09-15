"""/api/objects, /api/resolve-id."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app import objects as svc
from app.graph import neighbourhood

router = APIRouter(prefix="/api", tags=["objects"])


@router.get("/objects")
def list_objects(
    type: str | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    band: str | None = None,
    source: str | None = None,
):
    return svc.search_objects(type_=type, q=q, limit=limit, offset=offset, band=band, source=source)


@router.get("/resolve-id")
def resolve_id(scheme: str, value: str):
    obj = svc.resolve(scheme, value)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"no object for {scheme}={value}")
    return obj


@router.get("/objects/{object_id}")
def get_object(object_id: str):
    obj = svc.get_object(object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"unknown object {object_id}")
    return obj


@router.get("/objects/{object_id}/neighbourhood")
def object_neighbourhood(
    object_id: str,
    depth: int = Query(1, ge=1, le=3),
    lens: str | None = None,
    predicates: str | None = None,
    types: str | None = None,
    limit: int = Query(300, ge=1, le=5000),
):
    out = neighbourhood(object_id, depth=depth, lens=lens, predicates=predicates,
                        types=types, limit=limit)
    if not out.get("found"):
        raise HTTPException(status_code=404, detail=f"unknown object {object_id}")
    return out

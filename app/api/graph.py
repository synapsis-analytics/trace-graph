"""/api/graph, /api/path, /api/lenses."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.graph import shortest_path, whole_graph
from app.lenses import lens_definitions

router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/lenses")
def lenses():
    return {"lenses": lens_definitions()}


@router.get("/graph")
def graph(
    lens: str | None = None,
    types: str | None = None,
    predicates: str | None = None,
    limit: int = Query(2000, ge=1, le=5000),
    communities: bool = True,
):
    return whole_graph(lens=lens, types=types, predicates=predicates, limit=limit,
                       communities=communities)


@router.get("/path")
def path(
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
    lens: str | None = None,
    max_len: int = Query(6, ge=1, le=8),
):
    """CONTRACT: 404 only for unknown ids. "No valid path under this lens" is a 200 answer
    with an empty `paths` list and a plain-English `explanation`."""
    out = shortest_path(from_, to, lens=lens, max_len=max_len)
    if out.get("unknown_id"):
        raise HTTPException(status_code=404, detail=out.get("reason", "unknown object"))
    return out

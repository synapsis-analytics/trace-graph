"""/api/graph, /api/path, /api/lenses."""
from __future__ import annotations

from fastapi import APIRouter, Query

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
    return shortest_path(from_, to, lens=lens, max_len=max_len)

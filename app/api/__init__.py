"""FastAPI routers for the TRACE Graph API (PLAN §4)."""
from app.api import claims, graph, objects, ops  # noqa: F401

ROUTERS = [objects.router, graph.router, claims.router, ops.router]

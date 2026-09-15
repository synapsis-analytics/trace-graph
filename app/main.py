"""FastAPI application: API routers + MCP (streamable HTTP) + the built SPA."""
from __future__ import annotations

import contextlib
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from app import __version__
from app.api import ROUTERS
from app.config import get_settings
from app.db import init_db
from app.mcp_server import http_app as mcp_http_app

PLACEHOLDER = (
    "<!doctype html><html><head><meta charset='utf-8'><title>TRACE Graph</title></head>"
    "<body style='font-family:system-ui;margin:3rem'><h1>TRACE Graph</h1>"
    "<p>The API is running. The explorer UI is not built yet — run <code>npm ci && npm run build</code> "
    "in <code>frontend/</code>. See <a href='/docs'>/docs</a> for the API and <code>/mcp</code> for MCP.</p>"
    "</body></html>"
)

_taxonomy_cache: dict[str, Any] = {"at": 0.0, "value": None}

# The MCP session manager may only be run once per app, so the mounted ASGI app is rebuilt for
# every lifespan (uvicorn starts one; each TestClient context starts another).
_mcp_current: Any = None


async def _mcp_proxy(scope, receive, send):
    if _mcp_current is None:  # pragma: no cover - only before startup
        raise RuntimeError("MCP app is not running")
    await _mcp_current(scope, receive, send)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    global _mcp_current
    init_db()
    mcp_app = mcp_http_app("/")
    async with contextlib.AsyncExitStack() as stack:
        # the MCP app carries its own lifespan (the streamable-HTTP session manager)
        lifespan_ctx = getattr(getattr(mcp_app, "router", None), "lifespan_context", None)
        if lifespan_ctx is not None:
            await stack.enter_async_context(lifespan_ctx(mcp_app))
        _mcp_current = mcp_app
        try:
            yield
        finally:
            _mcp_current = None


app = FastAPI(
    title="TRACE Graph API",
    version=__version__,
    description=(
        "Taxonomy-Referenced Attestation & Continuous Evidence — an append-only claims registry "
        "and lineage graph over CGIAR portfolio knowledge. All data is public."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    allow_credentials=False,
)

for router in ROUTERS:
    app.include_router(router)

app.mount("/mcp", _mcp_proxy)


@app.api_route("/mcp", methods=["GET", "POST", "DELETE"], include_in_schema=False)
def mcp_root():
    """Clients that omit the trailing slash still reach the MCP endpoint."""
    return RedirectResponse("/mcp/", status_code=307)


def taxonomy_health(max_age: float = 30.0) -> dict[str, Any]:
    now = time.time()
    if _taxonomy_cache["value"] is not None and now - _taxonomy_cache["at"] < max_age:
        return _taxonomy_cache["value"]
    from app.taxonomy_client import get_client

    value = get_client().health()
    _taxonomy_cache.update({"at": now, "value": value})
    return value


@app.get("/health", tags=["meta"])
def health():
    from app.registry import counts

    settings = get_settings()
    c = counts()
    return {
        "status": "ok", "env": settings.env, "version": __version__,
        "objects": c["objects"], "links": c["links"], "claims": c["claims"],
        "taxonomy": taxonomy_health(),
        "public_url": settings.public_url,
        "db": str(settings.db_path),
        "frontend_built": settings.frontend_dist.exists(),
    }


@app.get("/", include_in_schema=False)
def index():
    dist = get_settings().frontend_dist
    index_file = dist / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse(PLACEHOLDER)


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    """Serve built SPA assets, falling back to index.html (client-side routing)."""
    if full_path.startswith(("api/", "mcp", "docs", "openapi.json", "health")):  # never SPA-serve these
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    dist: Path = get_settings().frontend_dist
    candidate = (dist / full_path).resolve()
    if dist.exists() and candidate.is_file() and str(candidate).startswith(str(dist.resolve())):
        return FileResponse(candidate)
    index_file = dist / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse(PLACEHOLDER)

"""MCP server for TRACE Graph (PLAN §4): thin wrappers over the same service functions.

Runs two ways:
  * mounted in FastAPI at ``/mcp`` (streamable HTTP) — see ``app/main.py``;
  * ``python -m app.mcp_server`` — stdio, for Claude Desktop / Claude Code.

The MCP Python SDK renamed ``FastMCP`` to ``MCPServer`` in 2.x; both are supported here.
"""
from __future__ import annotations

import json
from typing import Any

try:  # mcp >= 2.0
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # pragma: no cover - mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server  # type: ignore

from app import graph as graph_svc
from app import objects as obj_svc
from app.api.deps import check_key
from app.lenses import get_lens, lens_definitions
from app.registry import append_claim, list_claims
from app.tagging import tag_text as tag_text_svc

INSTRUCTIONS = (
    "TRACE Graph: an append-only claims registry and lineage graph over CGIAR portfolio knowledge "
    "(programs, areas of work, high-level outputs, indicators, outcomes, PRMS results, CGSpace "
    "knowledge products, innovations, institutions, countries, projects, MELIA studies, taxonomy "
    "concepts). Use lenses (portfolio, delivery, evidence, money, partnership) to keep paths "
    "meaningful: money never propagates across neighbours, and counts are always distinct by id."
)

server = _Server(name="trace-graph", instructions=INSTRUCTIONS)


# --------------------------------------------------------------------- tools
@server.tool(description="Full-text search of TRACE objects by label/description.")
def trace_search(query: str, type: str | None = None, limit: int = 20) -> dict[str, Any]:
    return obj_svc.search_objects(type_=type, q=query, limit=limit)


@server.tool(description="Fetch one TRACE object with its incoming/outgoing links and tags.")
def trace_get(id: str) -> dict[str, Any]:
    obj = obj_svc.get_object(id, with_claims=False)
    return obj or {"error": f"unknown object {id}"}


@server.tool(description="Neighbourhood of an object, optionally filtered by a lens (depth 1-3).")
def trace_neighbourhood(id: str, depth: int = 1, lens: str | None = None) -> dict[str, Any]:
    return graph_svc.neighbourhood(id, depth=depth, lens=lens, limit=200)


@server.tool(description="Shortest valid path between two objects under a lens, with a plain-English explanation.")
def trace_path(from_id: str, to_id: str, lens: str | None = None) -> dict[str, Any]:
    return graph_svc.shortest_path(from_id, to_id, lens=lens)


@server.tool(description="Resolve an alternate identifier (e.g. cgspace_handle, prms_result_id) to a TRACE object.")
def trace_resolve_id(scheme: str, value: str) -> dict[str, Any]:
    obj = obj_svc.resolve(scheme, value)
    return obj or {"error": f"no object for {scheme}={value}"}


@server.tool(description="Taxonomy coverage map: objects tagged per concept plus unmatched candidate terms.")
def trace_coverage(layer: str | None = None) -> dict[str, Any]:
    return graph_svc.coverage(layer=layer)


@server.tool(description="The lens definitions: allowed path patterns and their meaning.")
def trace_lenses() -> dict[str, Any]:
    return {"lenses": lens_definitions()}


@server.tool(description="List registry claims (status=review is the human review queue).")
def trace_claims(status: str | None = None, subject: str | None = None, limit: int = 50) -> dict[str, Any]:
    return list_claims(status=status, subject=subject, limit=limit)


@server.tool(description="Append a claim to the registry (JSON per the TRACE claim contract). Needs the access key.")
def trace_append_claim(claim_json: str, access_key: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    if not check_key(access_key):
        return {"error": "invalid or missing access_key"}
    try:
        claim = json.loads(claim_json) if isinstance(claim_json, str) else dict(claim_json)
    except json.JSONDecodeError as exc:
        return {"error": f"claim_json is not valid JSON: {exc}"}
    return append_claim(claim, dry_run=dry_run)


@server.tool(description="Resolve free text against the MELIAF taxonomy service (no claims written).")
def trace_tag_text(text: str) -> dict[str, Any]:
    return tag_text_svc(text)


@server.tool(description="Registry and graph statistics: counts by type, predicate, QA band and source.")
def trace_stats() -> dict[str, Any]:
    return obj_svc.stats()


# ----------------------------------------------------------------- resources
@server.resource("trace://object/{id}", description="A TRACE object as JSON.", mime_type="application/json")
def resource_object(id: str) -> str:
    obj = obj_svc.get_object(id, with_claims=False)
    return json.dumps(obj or {"error": f"unknown object {id}"}, indent=1, default=str)


@server.resource("trace://lens/{name}", description="A TRACE lens definition as JSON.", mime_type="application/json")
def resource_lens(name: str) -> str:
    lens = get_lens(name)
    if lens is None:
        return json.dumps({"error": f"unknown lens {name}", "available": [l["name"] for l in lens_definitions()]})
    public = {k: v for k, v in lens.items() if not k.startswith("_")}
    return json.dumps(public, indent=1, default=str)


TOOL_NAMES = ("trace_search", "trace_get", "trace_neighbourhood", "trace_path", "trace_resolve_id",
              "trace_coverage", "trace_lenses", "trace_claims", "trace_append_claim",
              "trace_tag_text", "trace_stats")


def http_app(path: str = "/"):
    """Starlette app for streamable HTTP mounting (stateless: no sticky sessions needed).

    DNS-rebinding protection is disabled because TRACE serves public data behind a reverse
    proxy/tunnel (the Host header is rewritten there); the write path is still key-protected.
    """
    try:
        from mcp.server.transport_security import TransportSecuritySettings

        security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False, allowed_hosts=["*"], allowed_origins=["*"]
        )
        return server.streamable_http_app(streamable_http_path=path, stateless_http=True,
                                          transport_security=security)
    except TypeError:  # pragma: no cover - mcp 1.x signature
        return server.streamable_http_app()


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()

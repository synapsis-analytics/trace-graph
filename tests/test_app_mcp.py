"""MCP server: tool listing, tool calls and resources (in-process client, no network)."""
from __future__ import annotations

import json

import mcp
import pytest

from app.mcp_server import TOOL_NAMES, server
from tests.conftest import IDS


def _schema(tool):
    return getattr(tool, "input_schema", None) or tool.inputSchema


async def _tools():
    async with mcp.Client(server) as c:
        return {t.name: t for t in (await c.list_tools()).tools}


async def _call(name: str, args: dict):
    async with mcp.Client(server) as c:
        result = await c.call_tool(name, args)
    payload = getattr(result, "structuredContent", None)
    if payload and "result" in payload:
        return payload["result"]
    if payload:
        return payload
    return json.loads(result.content[0].text)


async def test_tool_listing_matches_the_contract(seeded):
    tools = await _tools()
    assert set(tools) == set(TOOL_NAMES)
    assert all(tools[n].description for n in TOOL_NAMES)


async def test_tool_schemas_declare_required_arguments(seeded):
    tools = await _tools()
    assert _schema(tools["trace_get"])["required"] == ["id"]
    assert set(_schema(tools["trace_path"])["required"]) == {"from_id", "to_id"}


async def test_trace_search_tool(seeded):
    out = await _call("trace_search", {"query": "groundnut", "limit": 5})
    assert out["total"] >= 1
    assert any(i["id"] == IDS["result"] for i in out["items"])


async def test_trace_get_tool(seeded):
    out = await _call("trace_get", {"id": IDS["hlo"]})
    assert out["label"] == "Target markets" and out["attrs"]["budget_usd"] == 71200


async def test_trace_get_unknown(seeded):
    out = await _call("trace_get", {"id": "trace:hlo:nope"})
    assert "error" in out


async def test_trace_neighbourhood_tool(seeded):
    out = await _call("trace_neighbourhood", {"id": IDS["result"], "depth": 1, "lens": "delivery"})
    assert out["found"] and out["nodes"]


async def test_trace_path_tool(seeded):
    out = await _call("trace_path", {"from_id": IDS["result"], "to_id": IDS["program"],
                                     "lens": "delivery"})
    assert out["found"] and out["explanation"]


async def test_trace_resolve_id_tool(seeded):
    out = await _call("trace_resolve_id", {"scheme": "prms_result_id", "value": "24338"})
    assert out["id"] == IDS["result"]


async def test_trace_lenses_and_stats_tools(seeded):
    lenses = await _call("trace_lenses", {})
    assert len(lenses["lenses"]) == 5
    stats = await _call("trace_stats", {})
    assert stats["totals"]["objects"] == 23


async def test_trace_coverage_and_claims_tools(seeded):
    cov = await _call("trace_coverage", {"layer": "2"})
    assert cov["concepts"]
    claims = await _call("trace_claims", {"status": "review"})
    assert claims["total"] == 3


async def test_trace_tag_text_tool_degrades(seeded):
    out = await _call("trace_tag_text", {"text": "market intelligence"})
    assert out["reachable"] is False


async def test_append_claim_tool_requires_the_access_key(seeded):
    claim = json.dumps({"kind": "assert_object", "subject": "trace:country:ug",
                        "payload": {"type": "country", "label": "Uganda"}})
    denied = await _call("trace_append_claim", {"claim_json": claim})
    assert denied["error"].startswith("invalid or missing access_key")
    allowed = await _call("trace_append_claim", {"claim_json": claim, "access_key": "test-key",
                                                 "dry_run": True})
    assert allowed["qa"]["status"] == "accepted" and allowed["materialised"] is False


async def test_append_claim_tool_rejects_broken_json(seeded):
    out = await _call("trace_append_claim", {"claim_json": "{nope", "access_key": "test-key"})
    assert "not valid JSON" in out["error"]


async def test_resources_are_exposed(seeded):
    async with mcp.Client(server) as c:
        templates = await c.list_resource_templates()
        uris = {str(getattr(t, "uri_template", None) or t.uriTemplate) for t in getattr(templates, "resource_templates", None) or templates.resourceTemplates}
        assert uris == {"trace://object/{id}", "trace://lens/{name}"}
        obj = await c.read_resource(f"trace://object/{IDS['program']}")
        assert json.loads(obj.contents[0].text)["label"] == "Breeding for Tomorrow"
        lens = await c.read_resource("trace://lens/money")
        assert "boundary_attrs" in json.loads(lens.contents[0].text)


async def test_unknown_lens_resource(seeded):
    async with mcp.Client(server) as c:
        lens = await c.read_resource("trace://lens/nope")
    body = json.loads(lens.contents[0].text)
    assert "error" in body and "available" in body


def test_mcp_is_mounted_on_http(client):
    """The streamable-HTTP endpoint answers at /mcp (a bare GET is not a valid MCP request)."""
    resp = client.get("/mcp", follow_redirects=False)
    assert resp.status_code == 307 and resp.headers["location"] == "/mcp/"
    # a POST without the MCP Accept headers is refused immediately (no hanging SSE stream)
    bad = client.post("/mcp/", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert bad.status_code == 200 and "trace_search" in bad.text


@pytest.mark.parametrize("name", TOOL_NAMES)
def test_every_contract_tool_exists(name):
    assert name in TOOL_NAMES

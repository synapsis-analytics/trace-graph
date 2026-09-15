# TRACE Graph — MCP server

TRACE exposes the same knowledge to AI agents through the Model Context Protocol. The tools are
thin wrappers over the very same service functions the HTTP API uses, so an agent and a human see
identical answers.

Two transports:

| Transport | How | When |
|---|---|---|
| **streamable HTTP** | mounted in the FastAPI app at `/mcp` (trailing slash; `/mcp` 307-redirects) | remote agents, Claude Code over the tunnel |
| **stdio** | `python -m app.mcp_server` (or the `trace-mcp` console script) | Claude Desktop / local agents |

The HTTP transport is **stateless** (no sticky sessions) and DNS-rebinding protection is off
because the service sits behind a reverse proxy; reads are public, and `trace_append_claim`
requires the access key as a tool argument.

> SDK note: the MCP Python SDK renamed `FastMCP` to `MCPServer` in 2.x. `app/mcp_server.py`
> imports `mcp.server.mcpserver.MCPServer` and falls back to `mcp.server.fastmcp.FastMCP`, so it
> runs on both 1.x and 2.x. This prototype is built against `mcp 2.2.0`.

## Tools (names are the contract)

| Tool | Arguments | Returns |
|---|---|---|
| `trace_search` | `query`, `type?`, `limit?` | `{total, items[]}` |
| `trace_get` | `id` | object + `links_out`/`links_in`/`tags` |
| `trace_neighbourhood` | `id`, `depth?` (1–3), `lens?` | `{nodes, edges, truncated}` |
| `trace_path` | `from_id`, `to_id`, `lens?` | shortest path + plain-English `explanation` |
| `trace_resolve_id` | `scheme`, `value` | the object behind an alternate identifier |
| `trace_coverage` | `layer?` | taxonomy coverage + `unmatched_terms` |
| `trace_lenses` | – | the five lens definitions |
| `trace_claims` | `status?`, `subject?`, `limit?` | registry listing (`status="review"` = queue) |
| `trace_append_claim` | `claim_json`, `access_key`, `dry_run?` | the scored/stored claim |
| `trace_tag_text` | `text` | taxonomy matches for free text (no writes) |
| `trace_stats` | – | counts by type/predicate/band/source |

## Resources
* `trace://object/{id}` — one object as JSON.
* `trace://lens/{name}` — one lens definition as JSON (`portfolio`, `delivery`, `evidence`, `money`, `partnership`).

## Claude Desktop / Claude Code config

stdio (local checkout):
```json
{
  "mcpServers": {
    "trace-graph": {
      "command": "/Users/smithai/workspace/trace-graph/.venv/bin/python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/Users/smithai/workspace/trace-graph",
      "env": {
        "TRACE_DB_PATH": "/Users/smithai/workspace/trace-graph/data/trace.db",
        "TRACE_ACCESS_KEY": "…",
        "TAXONOMY_BASE_URL": "http://localhost:8420"
      }
    }
  }
}
```

streamable HTTP (deployed environment):
```json
{
  "mcpServers": {
    "trace-graph": {
      "type": "http",
      "url": "https://p8413.synaptic.synapsis-analytics.com/mcp/"
    }
  }
}
```
Claude Code one-liner: `claude mcp add --transport http trace-graph https://p8413.synaptic.synapsis-analytics.com/mcp/`

## Verifying from Python
```python
import asyncio, mcp
from app.mcp_server import server                      # in-process

async def main():
    async with mcp.Client(server) as c:                # or mcp.Client("http://127.0.0.1:8413/mcp/")
        print([t.name for t in (await c.list_tools()).tools])
        print((await c.call_tool("trace_stats", {})).structured_content)

asyncio.run(main())
```
Raw HTTP check (stateless, no initialize needed):
```bash
curl -s -X POST http://127.0.0.1:8413/mcp/ \
  -H 'content-type: application/json' -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Agent guidance baked into the server
The server's `instructions` tell the agent what TRACE is and that lenses matter: money never
propagates across neighbours, counts are distinct by id, and free text that does not comply with
the model is "off graph". Agents should prefer `trace_path`/`trace_neighbourhood` with an explicit
`lens` over raw search when the question is about how two things are connected.

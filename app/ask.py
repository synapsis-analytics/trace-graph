"""Optional LLM Q&A over the graph (PLAN D7). Deterministic tools, the model only orchestrates."""
from __future__ import annotations

import json
import re
from typing import Any

from app.config import get_settings

ID_RE = re.compile(r"trace:[a-z_]+:[a-z0-9][a-z0-9._-]*")

SYSTEM = (
    "You are TRACE Graph's analyst. Answer ONLY from the tools, which query a CGIAR claims registry "
    "and lineage graph (programs, areas of work, high-level outputs, results, knowledge products, "
    "partners, countries, projects, taxonomy concepts). Always cite the TRACE ids you used, e.g. "
    "trace:result:prms-24338. Respect the lens rules: money never propagates across neighbours and "
    "counts are distinct by id. If the tools do not contain the answer, say so plainly."
)

TOOLS: list[dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "trace_search", "description": "Full-text search objects by label/description.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}, "type": {"type": "string"}, "limit": {"type": "integer"}},
            "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "trace_get", "description": "Get one object with its links.",
        "parameters": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}}},
    {"type": "function", "function": {
        "name": "trace_neighbourhood", "description": "Neighbourhood of an object under a lens.",
        "parameters": {"type": "object", "properties": {
            "id": {"type": "string"}, "depth": {"type": "integer"}, "lens": {"type": "string"}},
            "required": ["id"]}}},
    {"type": "function", "function": {
        "name": "trace_path", "description": "Shortest explainable path between two objects under a lens.",
        "parameters": {"type": "object", "properties": {
            "from_id": {"type": "string"}, "to_id": {"type": "string"}, "lens": {"type": "string"}},
            "required": ["from_id", "to_id"]}}},
    {"type": "function", "function": {
        "name": "trace_stats", "description": "Counts by type, predicate, QA band and source.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "trace_lenses", "description": "The lens definitions (allowed path rules).",
        "parameters": {"type": "object", "properties": {}}}},
]


def call_tool(name: str, args: dict[str, Any]) -> Any:
    from app import graph as g
    from app import lenses as lz
    from app import objects as ob

    if name == "trace_search":
        return ob.search_objects(type_=args.get("type"), q=args.get("query"),
                                 limit=int(args.get("limit") or 10))
    if name == "trace_get":
        obj = ob.get_object(args["id"], with_claims=False)
        return obj or {"error": f"unknown object {args['id']}"}
    if name == "trace_neighbourhood":
        return g.neighbourhood(args["id"], depth=int(args.get("depth") or 1),
                               lens=args.get("lens"), limit=60)
    if name == "trace_path":
        return g.shortest_path(args["from_id"], args["to_id"], lens=args.get("lens"))
    if name == "trace_stats":
        return ob.stats()
    if name == "trace_lenses":
        return lz.lens_definitions()
    return {"error": f"unknown tool {name}"}


class AskUnavailable(RuntimeError):
    pass


def ask(question: str, max_rounds: int = 8) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise AskUnavailable("OPENAI_API_KEY not configured")
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": question},
    ]
    tool_calls_log: list[dict[str, Any]] = []
    model = settings.ask_model
    answer = ""
    for _ in range(max_rounds):
        try:
            resp = client.chat.completions.create(model=model, messages=messages, tools=TOOLS)
        except Exception as exc:
            if model != "gpt-4.1" and "model" in str(exc).lower():
                model = "gpt-4.1"
                continue
            raise
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))
        if not getattr(msg, "tool_calls", None):
            answer = msg.content or ""
            break
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = call_tool(tc.function.name, args)
            tool_calls_log.append({"name": tc.function.name, "arguments": args})
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, default=str)[:20000]})
    truncated = False
    if not answer:
        # The tool budget ran out while the model was still exploring. Never return an empty
        # answer: ask once more with the tools switched off so it has to conclude from what it has.
        truncated = True
        messages.append({
            "role": "user",
            "content": ("You have used the maximum number of tool calls. Answer now from the "
                        "evidence you already have, citing the TRACE ids you used, and say "
                        "explicitly what you could not verify."),
        })
        try:
            final = client.chat.completions.create(model=model, messages=messages,
                                                   tools=TOOLS, tool_choice="none")
            answer = final.choices[0].message.content or ""
        except Exception as exc:  # pragma: no cover - upstream failure
            answer = f"(no answer: the model stopped after {len(tool_calls_log)} tool calls — {exc})"
    cited = sorted(set(ID_RE.findall(answer)))
    return {"answer": answer, "model": model, "tool_calls": tool_calls_log,
            "objects_cited": cited, "tool_budget_exhausted": truncated}

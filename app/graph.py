"""Lineage graph services: neighbourhood, paths, whole-graph export, communities, coverage."""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict, deque
from typing import Any, Iterable

from app.db import connect
from app.ids import is_valid_id, type_of
from app.lenses import allowed_edge, explain_path, get_lens

MAX_GRAPH_NODES = 5000


# --------------------------------------------------------------------------- shaping

def node_size(degree: int) -> float:
    """CONTRACT: size = 1 + log(degree) (degree floored at 1 so isolated nodes still render)."""
    return round(1.0 + math.log(max(int(degree), 1)), 4)


def _node_json(row, degree: int = 1, community: int | None = None) -> dict[str, Any]:
    attrs = json.loads(row["attrs_json"] or "{}")
    qa = json.loads(row["qa_json"] or "{}")
    if community is not None:
        attrs = {**attrs, "community": community}
    attrs["degree"] = degree
    return {
        "id": row["id"], "type": row["type"], "label": row["label"] or row["id"],
        "size": node_size(degree), "band": qa.get("band"), "attrs": attrs,
    }


def _edge_json(row) -> dict[str, Any]:
    return {
        "id": row["id"], "source": row["subject"], "target": row["object"],
        "predicate": row["predicate"], "attrs": json.loads(row["attrs_json"] or "{}"),
        "band": (json.loads(row["qa_json"] or "{}") or {}).get("band"),
    }


def _split(csv: str | None) -> list[str]:
    return [x.strip() for x in (csv or "").split(",") if x.strip()]


def _degrees(conn, ids: Iterable[str]) -> dict[str, int]:
    ids = list(ids)
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    deg: dict[str, int] = defaultdict(int)
    for r in conn.execute(
        f"SELECT subject id, COUNT(*) c FROM links WHERE subject IN ({marks}) GROUP BY subject", ids
    ):
        deg[r["id"]] += r["c"]
    for r in conn.execute(
        f"SELECT object id, COUNT(*) c FROM links WHERE object IN ({marks}) GROUP BY object", ids
    ):
        deg[r["id"]] += r["c"]
    return deg


# --------------------------------------------------------------------------- neighbourhood

def neighbourhood(object_id: str, depth: int = 1, lens: str | None = None,
                  predicates: str | None = None, types: str | None = None,
                  limit: int = 300) -> dict[str, Any]:
    depth = max(1, min(int(depth), 3))
    limit = max(1, min(int(limit), MAX_GRAPH_NODES))
    pred_filter = set(_split(predicates))
    type_filter = set(_split(types))
    lens_spec = get_lens(lens)

    with connect(readonly=True) as conn:
        root = conn.execute("SELECT * FROM objects WHERE id=?", (object_id,)).fetchone()
        if root is None:
            return {"nodes": [], "edges": [], "truncated": False, "root": object_id, "found": False}
        seen = {object_id}
        frontier = [object_id]
        edges: dict[str, dict] = {}
        truncated = False
        for _ in range(depth):
            if not frontier or truncated:
                break
            marks = ",".join("?" * len(frontier))
            rows = conn.execute(
                f"SELECT * FROM links WHERE subject IN ({marks}) OR object IN ({marks})",
                [*frontier, *frontier],
            ).fetchall()
            next_frontier: list[str] = []
            for r in rows:
                if pred_filter and r["predicate"] not in pred_filter:
                    continue
                if lens_spec is not None and not allowed_edge(r["subject"], r["predicate"], r["object"], lens_spec):
                    continue
                other = r["object"] if r["subject"] in seen else r["subject"]
                if type_filter and is_valid_id(other) and type_of(other) not in type_filter:
                    continue
                edges[r["id"]] = _edge_json(r)
                for cand in (r["subject"], r["object"]):
                    if cand in seen:
                        continue
                    if len(seen) >= limit:
                        truncated = True
                        break
                    seen.add(cand)
                    next_frontier.append(cand)
                if truncated:
                    break
            frontier = next_frontier
        ids = list(seen)
        deg = _degrees(conn, ids)
        marks = ",".join("?" * len(ids))
        node_rows = conn.execute(f"SELECT * FROM objects WHERE id IN ({marks})", ids).fetchall()
        nodes = [_node_json(r, deg.get(r["id"], 0)) for r in node_rows]
    node_ids = {n["id"] for n in nodes}
    kept_edges = [e for e in edges.values() if e["source"] in node_ids and e["target"] in node_ids]
    return {
        "root": object_id, "found": True, "depth": depth, "lens": lens,
        "nodes": nodes, "edges": kept_edges, "truncated": truncated,
        "counts": {"nodes": len(nodes), "edges": len(kept_edges)},
    }


# --------------------------------------------------------------------------- paths

def shortest_path(from_id: str, to_id: str, lens: str | None = None, max_len: int = 6) -> dict[str, Any]:
    """BFS over the lens-filtered graph; edges are traversed both ways but reported with direction."""
    max_len = max(1, min(int(max_len), 8))
    lens_spec = get_lens(lens)
    with connect(readonly=True) as conn:
        if conn.execute("SELECT 1 FROM objects WHERE id=?", (from_id,)).fetchone() is None:
            return {"found": False, "unknown_id": from_id, "paths": [],
                    "reason": f"unknown object {from_id}",
                    "explanation": f"There is no object with id {from_id} in this graph."}
        if conn.execute("SELECT 1 FROM objects WHERE id=?", (to_id,)).fetchone() is None:
            return {"found": False, "unknown_id": to_id, "paths": [],
                    "reason": f"unknown object {to_id}",
                    "explanation": f"There is no object with id {to_id} in this graph."}
        prev: dict[str, tuple[str, dict, str]] = {}
        queue: deque[tuple[str, int]] = deque([(from_id, 0)])
        seen = {from_id}
        found = False
        while queue:
            cur, dist = queue.popleft()
            if cur == to_id:
                found = True
                break
            if dist >= max_len:
                continue
            rows = conn.execute(
                "SELECT * FROM links WHERE subject=? OR object=?", (cur, cur)
            ).fetchall()
            for r in rows:
                if lens_spec is not None and not allowed_edge(r["subject"], r["predicate"], r["object"], lens_spec):
                    continue
                nxt = r["object"] if r["subject"] == cur else r["subject"]
                direction = "out" if r["subject"] == cur else "in"
                if nxt in seen:
                    continue
                seen.add(nxt)
                prev[nxt] = (cur, dict(r), direction)
                queue.append((nxt, dist + 1))
        if not found:
            lens_name = lens or "any lens"
            reason = f"no path under lens '{lens}' within {max_len} hops"
            explanation = (
                f"No valid path: the lens '{lens_name}' does not allow any chain of up to "
                f"{max_len} links between these two objects. That is an answer, not an error — "
                f"lenses deliberately refuse path types that would not be meaningful "
                f"(for example the money lens never traverses result -> country)."
                if lens else
                f"No path of {max_len} links or fewer connects these two objects."
            )
            return {"found": False, "from": from_id, "to": to_id, "lens": lens, "paths": [],
                    "reason": reason, "explanation": explanation}
        chain: list[tuple[str, dict, str]] = []
        cur = to_id
        while cur != from_id:
            parent, row, direction = prev[cur]
            chain.append((parent, row, direction, cur))  # type: ignore[arg-type]
            cur = parent
        chain.reverse()
        node_ids = {from_id, to_id}
        for parent, row, _d, child in chain:  # type: ignore[misc]
            node_ids.update([parent, child])
        marks = ",".join("?" * len(node_ids))
        node_rows = {r["id"]: r for r in conn.execute(
            f"SELECT * FROM objects WHERE id IN ({marks})", list(node_ids))}
        deg = _degrees(conn, node_ids)

    def simple(nid: str) -> dict:
        r = node_rows[nid]
        return {"id": nid, "type": r["type"], "label": r["label"] or nid}

    steps = []
    edges = []
    for parent, row, direction, child in chain:  # type: ignore[misc]
        steps.append({
            "from": simple(parent), "predicate": row["predicate"], "direction": direction,
            "to": simple(child),
            "attrs": json.loads(row["attrs_json"] or "{}"),
        })
        edges.append({"id": row["id"], "source": row["subject"], "target": row["object"],
                      "predicate": row["predicate"], "attrs": json.loads(row["attrs_json"] or "{}")})
    nodes = [_node_json(node_rows[nid], deg.get(nid, 0)) for nid in
             [from_id] + [c[3] for c in chain]]  # type: ignore[misc]
    hops = [{"from": s_["from"]["id"], "predicate": s_["predicate"], "to": s_["to"]["id"],
             "direction": s_["direction"]} for s_ in steps]
    path = {
        "length": len(steps), "hops": hops, "steps": steps, "nodes": nodes, "edges": edges,
        "explanation": explain_path(steps),
    }
    return {"found": True, "from": from_id, "to": to_id, "lens": lens, "paths": [path],
            "explanation": path["explanation"]}


# --------------------------------------------------------------------------- whole graph

def detect_communities(nodes: list[dict], edges: list[dict]) -> dict[str, int]:
    """greedy modularity (networkx); falls back to python-louvain, then to a single community."""
    if not nodes:
        return {}
    try:
        import networkx as nx

        g = nx.Graph()
        g.add_nodes_from([n["id"] for n in nodes])
        g.add_edges_from([(e["source"], e["target"]) for e in edges
                          if e["source"] != e["target"]])
        from networkx.algorithms.community import greedy_modularity_communities

        comms = greedy_modularity_communities(g)
        return {nid: i for i, com in enumerate(comms) for nid in com}
    except Exception:
        pass
    try:  # pragma: no cover - fallback path
        import community as community_louvain
        import networkx as nx

        g = nx.Graph()
        g.add_nodes_from([n["id"] for n in nodes])
        g.add_edges_from([(e["source"], e["target"]) for e in edges])
        return community_louvain.best_partition(g)
    except Exception:  # pragma: no cover
        return {n["id"]: 0 for n in nodes}


def whole_graph(lens: str | None = None, types: str | None = None, limit: int = 2000,
                predicates: str | None = None, communities: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit), MAX_GRAPH_NODES))
    type_filter = _split(types)
    pred_filter = set(_split(predicates))
    lens_spec = get_lens(lens)
    with connect(readonly=True) as conn:
        params: list[Any] = []
        clause = ""
        if type_filter:
            clause = "WHERE type IN (%s)" % ",".join("?" * len(type_filter))
            params = list(type_filter)
        total_nodes = conn.execute(f"SELECT COUNT(*) c FROM objects {clause}", params).fetchone()["c"]
        rows = conn.execute(
            f"""SELECT o.* FROM objects o {clause}
                ORDER BY (SELECT COUNT(*) FROM links l WHERE l.subject=o.id OR l.object=o.id) DESC
                LIMIT ?""",
            [*params, limit],
        ).fetchall()
        ids = [r["id"] for r in rows]
        deg = _degrees(conn, ids)
        idset = set(ids)
        edge_rows = conn.execute("SELECT * FROM links").fetchall()
        edges = []
        for r in edge_rows:
            if r["subject"] not in idset or r["object"] not in idset:
                continue
            if pred_filter and r["predicate"] not in pred_filter:
                continue
            if lens_spec is not None and not allowed_edge(r["subject"], r["predicate"], r["object"], lens_spec):
                continue
            edges.append(_edge_json(r))
        nodes = [_node_json(r, deg.get(r["id"], 0)) for r in rows]
    if communities:
        part = detect_communities(nodes, edges)
        for n in nodes:
            n["attrs"]["community"] = int(part.get(n["id"], 0))
    return {
        "nodes": nodes, "edges": edges, "lens": lens,
        "truncated": total_nodes > len(nodes),
        "counts": {"nodes": len(nodes), "edges": len(edges), "total_objects": total_nodes},
    }


# --------------------------------------------------------------------------- coverage

def coverage(layer: str | int | None = None, group: str | None = None, limit: int = 200) -> dict[str, Any]:
    """Taxonomy coverage map: per concept → #objects tagged (by type) + unmatched candidate terms."""
    layer = str(layer) if layer not in (None, "") else None
    with connect(readonly=True) as conn:
        rows = conn.execute(
            """SELECT l.object AS concept_id, c.label AS concept_label, c.attrs_json AS concept_attrs,
                      o.type AS obj_type, COUNT(*) AS n
                 FROM links l
                 JOIN objects c ON c.id = l.object
                 JOIN objects o ON o.id = l.subject
                WHERE l.predicate='TAGGED_WITH'
             GROUP BY l.object, o.type"""
        ).fetchall()
        concepts: dict[str, dict] = {}
        for r in rows:
            attrs = json.loads(r["concept_attrs"] or "{}")
            clayer = str(attrs.get("layer", ""))
            if layer and clayer != layer:
                continue
            if group and str(attrs.get("group", "")) != group:
                continue
            c = concepts.setdefault(r["concept_id"], {
                "id": r["concept_id"], "label": r["concept_label"], "layer": clayer,
                "uri": attrs.get("uri"),
                "group": attrs.get("group"), "by_type": {}, "objects": 0, "count": 0,
            })
            c["by_type"][r["obj_type"]] = r["n"]
            c["objects"] += r["n"]
            c["count"] = c["objects"]
        untagged = conn.execute(
            """SELECT type, COUNT(*) c FROM objects o
                WHERE o.type IN ('result','kp','hlo','outcome','innovation')
                  AND NOT EXISTS (SELECT 1 FROM links l WHERE l.subject=o.id AND l.predicate='TAGGED_WITH')
             GROUP BY type"""
        ).fetchall()
        cand_rows = conn.execute(
            "SELECT id, payload_json, subject, status FROM claims WHERE kind='candidate_concept'"
        ).fetchall()
        taggable = conn.execute(
            """SELECT COUNT(*) c FROM objects WHERE type IN ('result','kp','hlo','outcome','innovation')"""
        ).fetchone()["c"]
    counter: Counter = Counter()
    candidates: dict[str, dict] = {}
    for r in cand_rows:
        payload = json.loads(r["payload_json"] or "{}")
        term = (payload.get("term") or payload.get("label") or r["subject"] or "").strip()
        if not term:
            continue
        attrs = payload.get("attrs") or {}
        # `hits` = how many object labels the free term was seen in (taxonomy channel)
        counter[term] += int(attrs.get("hits") or payload.get("count") or 1)
        # `example` must be a TRACE id the UI can focus; candidate concepts do not materialise,
        # so we offer the payload id only when it actually resolves, otherwise contexts (text).
        example = payload.get("example") or attrs.get("example")
        cand = candidates.setdefault(term, {"term": term, "count": 0, "status": r["status"],
                                            "claim_id": r["id"],
                                            "example": example,
                                            "contexts": (attrs.get("contexts") or [])[:5],
                                            "suggested_layer": attrs.get("suggested_layer"),
                                            "suggested_for": payload.get("suggested_for"),
                                            "layer": payload.get("layer", "1")})
        if cand.get("example") is None and example:
            cand["example"] = example
        cand["count"] = counter[term]
    ranked = sorted(concepts.values(), key=lambda c: -c["objects"])[:limit]
    untagged_map = {r["type"]: r["c"] for r in untagged}
    tagged_objects = taggable - sum(untagged_map.values())
    return {
        "layer": layer, "group": group,
        "concepts": ranked,
        "concept_count": len(concepts),
        "unmatched_terms": sorted(candidates.values(), key=lambda c: -c["count"])[:limit],
        "untagged_by_type": untagged_map,
        "coverage_pct": round(100.0 * tagged_objects / taggable, 1) if taggable else 0.0,
        "taggable_objects": taggable, "tagged_objects": tagged_objects,
        "totals": {"tagged_objects": tagged_objects, "objects": taggable,
                   "concepts": len(concepts)},
    }


# --------------------------------------------------------------------------- export

def export_graph(version: str | None = None) -> dict[str, Any]:
    g = whole_graph(limit=MAX_GRAPH_NODES, communities=False)
    return {"version": version, "nodes": g["nodes"], "edges": g["edges"], "counts": g["counts"]}

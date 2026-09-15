"""Graph services: neighbourhood, lens filtering, truncation, paths, communities, coverage."""
from __future__ import annotations

from app.graph import coverage, neighbourhood, node_size, shortest_path, whole_graph
from app.lenses import allowed, explain_path, lens_definitions, lens_names
from tests.conftest import IDS


def test_node_size_is_one_plus_log_degree():
    assert node_size(1) == 1.0
    assert node_size(0) == 1.0          # isolated nodes still render
    assert node_size(10) > node_size(5)


def test_neighbourhood_depth_one(seeded):
    out = neighbourhood(IDS["result"], depth=1)
    assert out["found"] and out["truncated"] is False
    ids = {n["id"] for n in out["nodes"]}
    assert IDS["kp"] in ids and IDS["institution"] in ids and IDS["program"] in ids
    assert IDS["aow"] not in ids        # two hops away


def test_neighbourhood_depth_two_reaches_further(seeded):
    out = neighbourhood(IDS["result"], depth=2)
    assert IDS["aow"] in {n["id"] for n in out["nodes"]}


def test_neighbourhood_lens_filtering(seeded):
    delivery = neighbourhood(IDS["result"], depth=1, lens="delivery")
    evidence = neighbourhood(IDS["result"], depth=1, lens="evidence")
    d_ids = {n["id"] for n in delivery["nodes"]}
    e_ids = {n["id"] for n in evidence["nodes"]}
    assert IDS["country"] in d_ids and IDS["kp"] not in d_ids
    assert IDS["kp"] in e_ids and IDS["country"] not in e_ids


def test_money_lens_never_traverses_result_to_country(seeded):
    assert allowed("LOCATED_IN", "result", "country", "delivery") is True
    assert allowed("LOCATED_IN", "result", "country", "money") is False
    out = neighbourhood(IDS["result"], depth=3, lens="money")
    assert IDS["country"] not in {n["id"] for n in out["nodes"]}


def test_neighbourhood_predicate_filter(seeded):
    out = neighbourhood(IDS["result"], depth=1, predicates="WITH_PARTNER")
    assert {e["predicate"] for e in out["edges"]} == {"WITH_PARTNER"}


def test_neighbourhood_type_filter(seeded):
    out = neighbourhood(IDS["result"], depth=1, types="institution")
    types = {n["type"] for n in out["nodes"]} - {"result"}
    assert types == {"institution"}


def test_neighbourhood_truncation_flag(seeded):
    out = neighbourhood(IDS["program"], depth=3, limit=3)
    assert out["truncated"] is True
    assert len(out["nodes"]) <= 3


def test_unknown_object_neighbourhood(seeded):
    out = neighbourhood("trace:result:prms-000", depth=1)
    assert out["found"] is False and out["nodes"] == []


def test_shortest_path_with_explanation(seeded):
    out = shortest_path(IDS["result"], IDS["program"], lens="delivery")
    assert out["found"] and out["paths"]
    assert out["explanation"].startswith("Result ")
    assert out["explanation"].endswith(".")


def test_path_reports_direction(seeded):
    out = shortest_path(IDS["program"], IDS["result"], lens="delivery")
    step = out["paths"][0]["steps"][0]
    assert step["direction"] in ("in", "out")
    assert "is the reporting programme of" in out["explanation"] or "contains" in out["explanation"]


def test_path_respects_the_lens(seeded):
    assert shortest_path(IDS["result"], IDS["country"], lens="delivery")["found"] is True
    assert shortest_path(IDS["result"], IDS["country"], lens="money")["found"] is False


def test_path_unknown_endpoint(seeded):
    out = shortest_path(IDS["result"], "trace:country:zz")
    assert out["found"] is False and "unknown object" in out["reason"]


def test_explain_path_is_readable():
    steps = [
        {"from": {"label": "Brief", "type": "result"}, "predicate": "CONTRIBUTES_TO",
         "direction": "out", "to": {"label": "Target markets", "type": "hlo"}},
        {"from": {"label": "Target markets", "type": "hlo"}, "predicate": "PART_OF",
         "direction": "out", "to": {"label": "Market Intelligence", "type": "aow"}},
    ]
    text = explain_path(steps)
    assert text == ('Result "Brief" contributes to High-Level Output "Target markets", '
                    'which is part of Area of Work "Market Intelligence".')


def test_whole_graph_shape_and_communities(seeded):
    g = whole_graph(limit=500)
    assert g["counts"]["nodes"] == 23
    node = g["nodes"][0]
    assert set(node) >= {"id", "type", "label", "size", "band", "attrs"}
    assert "community" in node["attrs"]
    edge = g["edges"][0]
    assert set(edge) >= {"id", "source", "target", "predicate", "attrs"}


def test_whole_graph_type_filter(seeded):
    g = whole_graph(types="result,kp", limit=100)
    assert {n["type"] for n in g["nodes"]} == {"result", "kp"}
    assert g["truncated"] is False
    assert whole_graph(types="result,kp", limit=2)["truncated"] is True


def test_whole_graph_lens_filter_drops_edges(seeded):
    full = whole_graph(limit=500)
    portfolio = whole_graph(lens="portfolio", limit=500)
    assert len(portfolio["edges"]) < len(full["edges"])
    assert {e["predicate"] for e in portfolio["edges"]} <= {"PART_OF", "SYNERGY_WITH"}


def test_lens_catalogue():
    names = lens_names()
    assert names == ["delivery", "evidence", "money", "partnership", "portfolio"]
    defs = {d["name"]: d for d in lens_definitions()}
    assert defs["money"]["boundary_attrs"] == ["budget_usd", "amount_usd", "target", "share_pct"]
    assert all(d["description"] for d in defs.values())
    assert all("_steps" not in d for d in defs.values())


def test_coverage_map(seeded):
    cov = coverage()
    ids = {c["id"] for c in cov["concepts"]}
    assert IDS["concept"] in ids
    assert cov["concepts"][0]["by_type"]
    assert cov["unmatched_terms"][0]["term"] == "maize seed systems"
    assert 0 < cov["coverage_pct"] <= 100


def test_coverage_layer_filter(seeded):
    assert coverage(layer="2")["concept_count"] >= 1
    assert coverage(layer="9")["concept_count"] == 0

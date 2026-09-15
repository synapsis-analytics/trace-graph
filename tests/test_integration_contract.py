"""WP-I contract alignment tests: the exact shapes the SPA reads, the per-type duplicate
threshold, and the keyword-callable ingest entry points (PLAN §4 + wave-1 handover items)."""
from __future__ import annotations

import importlib
import inspect

import pytest
import yaml

from tests.conftest import IDS

CHANNELS = ("prms", "cgspace", "porb", "toc", "taxonomy")


# --------------------------------------------------------------- object detail: neighbours

def test_object_links_carry_denormalised_neighbour(client):
    obj = client.get(f"/api/objects/{IDS['result']}").json()
    assert obj["links_out"] and obj["links_in"] is not None
    for link in obj["links_out"] + obj["links_in"]:
        n = link.get("neighbour")
        assert n and n["id"] and n["id"] != obj["id"]
        assert set(n) >= {"id", "label", "type"}
        assert link["subject"] and link["object"]
    out_ids = {l["neighbour"]["id"] for l in obj["links_out"]}
    assert {l["object"] for l in obj["links_out"]} == out_ids


def test_tags_are_concept_shaped(client):
    obj = client.get(f"/api/objects/{IDS['result']}").json()
    for tag in obj["tags"]:
        assert tag["id"].startswith("trace:concept:")
        assert "label" in tag and "via" in tag


# --------------------------------------------------------------- path contract

def test_path_returns_hops_and_explanation(client):
    body = client.get("/api/path", params={"from": IDS["result"], "to": IDS["program"],
                                           "lens": "delivery"}).json()
    assert body["paths"], body
    p = body["paths"][0]
    assert p["hops"] and len(p["hops"]) == p["length"]
    assert set(p["hops"][0]) >= {"from", "predicate", "to"}
    assert body["explanation"]


def test_blocked_lens_is_a_200_answer_not_a_404(client):
    r = client.get("/api/path", params={"from": IDS["result"], "to": IDS["country"],
                                        "lens": "money"})
    assert r.status_code == 200
    body = r.json()
    assert body["paths"] == []
    assert body["explanation"] and "money" in body["explanation"].lower()


def test_unknown_id_is_a_404(client):
    r = client.get("/api/path", params={"from": "trace:result:nope", "to": IDS["program"]})
    assert r.status_code == 404


# --------------------------------------------------------------- coverage contract

def test_coverage_shape(client):
    body = client.get("/api/coverage").json()
    assert "concepts" in body and "unmatched_terms" in body
    for c in body["concepts"]:
        assert c["count"] == c["objects"] and isinstance(c["by_type"], dict)
    assert set(body["totals"]) >= {"tagged_objects", "objects"}
    for u in body["unmatched_terms"]:
        assert u["term"] and u["count"] >= 1 and "example" in u


# --------------------------------------------------------------- QA: per-type duplicates

def test_person_is_exempt_from_the_fuzzy_duplicate_check():
    from app.qa import fuzzy_threshold_for

    rules = yaml.safe_load(open("qa/rules.yaml", encoding="utf-8"))
    assert fuzzy_threshold_for("person", rules) is None
    assert fuzzy_threshold_for("institution", rules) == 95
    assert fuzzy_threshold_for("result", rules) == rules["fuzzy_duplicate_threshold"]


def test_near_duplicate_person_is_accepted_but_result_is_reviewed(client, key_headers):
    def append(type_, slug, label):
        claim = {
            "kind": "assert_object", "subject": f"trace:{type_}:{slug}",
            "payload": {"id": f"trace:{type_}:{slug}", "type": type_, "label": label},
            "attested_by": "agent:test", "provenance": "recorded",
        }
        return client.post("/api/claims", json=claim, headers=key_headers,
                           params={"dry_run": 1}).json()

    client.post("/api/claims", headers=key_headers, json={
        "kind": "assert_object", "subject": "trace:person:orcid-0000-0001",
        "payload": {"id": "trace:person:orcid-0000-0001", "type": "person",
                    "label": "Maria Gonzalez Rodriguez"},
        "attested_by": "agent:test", "provenance": "recorded"})
    client.post("/api/claims", headers=key_headers, json={
        "kind": "assert_object", "subject": "trace:result:prms-99001",
        "payload": {"id": "trace:result:prms-99001", "type": "result",
                    "label": "Market segmentation of maize seed systems in Kenya"},
        "attested_by": "agent:test", "provenance": "recorded"})

    person = append("person", "orcid-0000-0002", "Maria Gonzalez Rodriguez")
    dup_check = next(c for c in person["qa"]["checks"] if c["name"] == "duplicate")
    assert dup_check["ok"] is True and "exempt" in dup_check["note"]

    result = append("result", "prms-99002", "Market segmentation of maize seed systems in Kenya")
    dup_check = next(c for c in result["qa"]["checks"] if c["name"] == "duplicate")
    assert dup_check["ok"] is False


# --------------------------------------------------------------- ingest entry points

@pytest.mark.parametrize("channel", CHANNELS)
def test_every_channel_has_a_keyword_callable_entry_point(channel):
    mod = importlib.import_module(f"ingest.{channel}")
    fn = getattr(mod, "run_channel")
    sig = inspect.signature(fn)
    assert "limit" in sig.parameters
    bound = sig.bind(limit=5, load=False)     # must be callable by keyword only
    assert bound.arguments["limit"] == 5


def test_ingest_endpoint_falls_back_to_replay_when_the_source_is_absent(client, key_headers,
                                                                       monkeypatch):
    import ingest.prms as prms

    def boom(*_a, **_kw):
        raise FileNotFoundError("no PRMS snapshot on this machine")

    monkeypatch.setattr(prms, "run", boom)
    body = client.post("/api/ingest/prms", json={"limit": 1}, headers=key_headers).json()
    summary = body["summary"]
    assert summary["mode"] == "replay-batches"
    assert "no PRMS snapshot" in summary["error"]


def test_ingest_requires_a_key(client):
    assert client.post("/api/ingest/prms", json={}).status_code == 401


# --------------------------------------------------------------- env / packaging hygiene

def test_env_example_documents_every_setting():
    text = open(".env.example", encoding="utf-8").read()
    for key in ("TRACE_ENV", "PORT", "TRACE_DB_PATH", "TRACE_DATA_DIR", "TRACE_ACCESS_KEY",
                "TAXONOMY_BASE_URL", "OPENAI_API_KEY", "TRACE_ASK_MODEL", "TRACE_PUBLIC_URL"):
        assert f"{key}=" in text


def test_mcp_pin_matches_the_installed_sdk():
    from importlib.metadata import version

    req = open("requirements.txt", encoding="utf-8").read()
    assert "mcp>=2.0" in req
    assert int(version("mcp").split(".")[0]) >= 2

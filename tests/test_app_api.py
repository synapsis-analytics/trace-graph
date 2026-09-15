"""HTTP API contract tests (PLAN §4): shapes, filters, access-key enforcement, degradation."""
from __future__ import annotations

from tests.conftest import IDS


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["env"] == "test"
    assert body["objects"] == 23 and body["claims"] == 58
    assert set(body["taxonomy"]) >= {"url", "reachable", "version"}
    assert body["taxonomy"]["reachable"] is False       # no network in tests


def test_openapi_docs(client):
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200


def test_stats(client):
    s = client.get("/api/stats").json()
    assert s["totals"]["objects"] == 23
    assert s["objects_by_type"]["result"] == 3
    assert s["links_by_predicate"]["PART_OF"] == 4
    assert s["claims_by_band"]["high"] >= 50
    assert s["claims_by_status"]["review"] == 3


def test_list_objects_and_fts(client):
    all_objs = client.get("/api/objects", params={"limit": 100}).json()
    assert all_objs["total"] == 23 and len(all_objs["items"]) == 23
    hit = client.get("/api/objects", params={"q": "market segmentation"}).json()
    assert hit["total"] >= 1
    assert any(i["id"] == IDS["result"] for i in hit["items"])


def test_list_objects_type_filter_and_paging(client):
    page = client.get("/api/objects", params={"type": "result", "limit": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 2
    page2 = client.get("/api/objects", params={"type": "result", "limit": 2, "offset": 2}).json()
    assert len(page2["items"]) == 1


def test_object_detail_contract(client):
    obj = client.get(f"/api/objects/{IDS['result']}").json()
    assert obj["type"] == "result" and obj["attrs"]["result_type"] == "Knowledge product"
    assert {"links_out", "links_in", "claims", "tags", "alt_ids", "qa"} <= set(obj)
    assert any(l["predicate"] == "SAME_AS" and l["object"] == IDS["kp"] for l in obj["links_out"])
    assert obj["links_out"][0]["label"]
    assert obj["tags"] and obj["tags"][0]["predicate"] == "TAGGED_WITH"
    assert obj["claim_count"] >= 5


def test_object_404(client):
    assert client.get("/api/objects/trace:result:prms-000").status_code == 404


def test_resolve_id(client):
    obj = client.get("/api/resolve-id", params={"scheme": "prms_result_id", "value": "24338"}).json()
    assert obj["id"] == IDS["result"]
    handle = client.get("/api/resolve-id",
                        params={"scheme": "cgspace_handle",
                                "value": "https://hdl.handle.net/10568/175922"}).json()
    assert handle["id"] == IDS["kp"]
    assert client.get("/api/resolve-id", params={"scheme": "doi", "value": "nope"}).status_code == 404


def test_neighbourhood_endpoint(client):
    out = client.get(f"/api/objects/{IDS['result']}/neighbourhood",
                     params={"depth": 2, "lens": "delivery"}).json()
    assert {"nodes", "edges", "truncated"} <= set(out)
    assert out["nodes"][0]["size"] >= 1.0
    assert client.get("/api/objects/trace:result:x/neighbourhood").status_code == 404


def test_graph_endpoint(client):
    g = client.get("/api/graph", params={"limit": 100}).json()
    assert g["counts"]["nodes"] == 23 and g["edges"]
    assert all({"id", "source", "target", "predicate"} <= set(e) for e in g["edges"])


def test_path_endpoint(client):
    out = client.get("/api/path", params={"from": IDS["result"], "to": IDS["aow"],
                                          "lens": "delivery"}).json()
    assert out["found"] and out["paths"][0]["length"] >= 2
    assert "Area of Work" in out["explanation"]


def test_lenses_endpoint(client):
    lenses = client.get("/api/lenses").json()["lenses"]
    assert [l["name"] for l in lenses] == ["delivery", "evidence", "money", "partnership", "portfolio"]
    assert lenses[0]["paths"]


def test_claims_listing_and_review_queue(client):
    all_claims = client.get("/api/claims", params={"limit": 200}).json()
    assert all_claims["total"] == 58
    review = client.get("/api/claims", params={"status": "review"}).json()
    assert review["total"] == 3
    assert all(c["qa"]["status"] in ("review", "accepted", "rejected") for c in review["items"])
    by_kind = client.get("/api/claims", params={"kind": "assert_link", "limit": 200}).json()
    assert by_kind["total"] >= 25


def test_claim_detail_and_404(client):
    claim = client.get("/api/claims/clm_FIXTURERETR1").json()
    assert claim["kind"] == "retract" and claim["supersedes"] == "clm_FIXTUREGEO1"
    assert claim["qa"]["checks"]
    assert client.get("/api/claims/clm_NOPE").status_code == 404


def test_post_claim_requires_access_key(client):
    body = {"kind": "assert_object", "subject": "trace:country:ug",
            "payload": {"type": "country", "label": "Uganda"}}
    assert client.post("/api/claims", json=body).status_code == 401
    assert client.post("/api/claims", json=body, headers={"X-Access-Key": "wrong"}).status_code == 401


def test_post_claim_dry_run_then_real(client, key_headers):
    body = {"kind": "assert_object", "subject": "trace:country:ug",
            "payload": {"type": "country", "label": "Uganda",
                        "alt_ids": [{"scheme": "iso2", "value": "UG"}]},
            "provenance": "signed", "attested_by": "person:tester"}
    dry = client.post("/api/claims", params={"dry_run": 1}, json=body, headers=key_headers).json()
    assert dry["materialised"] is False
    assert client.get("/api/objects/trace:country:ug").status_code == 404
    real = client.post("/api/claims", json=body, headers=key_headers).json()
    assert real["status"] == "accepted" and real["materialised"] is True
    assert client.get("/api/objects/trace:country:ug").status_code == 200


def test_post_claim_validation_error(client, key_headers):
    bad = client.post("/api/claims", json={"kind": "nonsense", "subject": "x"}, headers=key_headers)
    assert bad.status_code == 422


def test_decide_endpoint(client, key_headers):
    review = client.get("/api/claims", params={"status": "review", "kind": "assert_object"}).json()
    claim_id = review["items"][0]["id"]
    assert client.post(f"/api/claims/{claim_id}/decide",
                       json={"decision": "accept", "by": "person:test"}).status_code == 401
    out = client.post(f"/api/claims/{claim_id}/decide",
                      json={"decision": "accept", "by": "person:test", "note": "checked"},
                      headers=key_headers).json()
    assert out["status"] == "accepted" and out["decided_by"] == "person:test"
    assert client.post("/api/claims/clm_NOPE/decide", json={"decision": "accept"},
                       headers=key_headers).status_code == 404


def test_coverage_endpoint(client):
    cov = client.get("/api/coverage", params={"layer": "2"}).json()
    assert cov["concepts"] and cov["unmatched_terms"]
    assert "untagged_by_type" in cov


def test_tag_endpoint_degrades_without_taxonomy(client, key_headers):
    out = client.post("/api/tag", json={"text": "market intelligence for maize"},
                      headers=key_headers).json()
    assert out["reachable"] is False and out["source"] == "offline-copy"
    assert isinstance(out["matches"], list)
    assert client.post("/api/tag", json={}, headers=key_headers).status_code == 400


def test_ingest_unknown_channel_and_missing_module(client, key_headers):
    assert client.post("/api/ingest/nope", json={}, headers=key_headers).status_code == 404
    resp = client.post("/api/ingest/toc", json={}, headers=key_headers)
    assert resp.status_code in (200, 501)      # 501 until the DATA agent ships that channel


def test_ask_returns_503_without_key(client):
    resp = client.post("/api/ask", json={"question": "who partnered on the groundnut brief?"})
    assert resp.status_code == 503
    assert resp.json()["detail"] == "OPENAI_API_KEY not configured"


def test_spa_placeholder_and_unknown_api_path(client):
    root = client.get("/")
    assert root.status_code == 200 and "TRACE Graph" in root.text
    assert client.get("/api/does-not-exist").status_code == 404
    assert client.get("/explorer").status_code == 200        # SPA fallback


def test_cors_headers(client):
    resp = client.get("/api/stats", headers={"Origin": "http://localhost:5173"})
    assert resp.headers["access-control-allow-origin"] == "*"

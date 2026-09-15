"""WP-D: contract tests over the committed seed claim batches (data/claims/seed-*.jsonl).

These are the guards that matter for the registry: every claim is schema-valid, no object id is
asserted twice inside one batch, every link endpoint resolves inside the seed, and the PORB
**budget never appears on a link** (the money-boundary rule, CONTRACT §3.6).
"""
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

os.environ.setdefault("TRACE_INGEST_NOW", "2026-09-15T20:00:00Z")

import pytest  # noqa: E402

from ingest import common as C  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CLAIMS_DIR = ROOT / "data" / "claims"
SEED_DIR = ROOT / "data" / "seed"
BATCHES = sorted(CLAIMS_DIR.glob("seed-*.jsonl"))

pytestmark = pytest.mark.skipif(not BATCHES, reason="seed batches not generated yet")


@pytest.fixture(scope="module")
def all_claims() -> dict[str, list[dict]]:
    return {p.name: C.read_batch(p) for p in BATCHES}


def test_all_five_channels_present():
    assert {p.stem for p in BATCHES} == {
        "seed-prms", "seed-cgspace", "seed-porb", "seed-toc", "seed-taxonomy"}


def test_every_claim_is_schema_valid(all_claims):
    problems = []
    for name, claims in all_claims.items():
        for c in claims:
            for err in C.validate_claim(c):
                problems.append(f"{name}:{c.get('id')} {err}")
    assert problems[:5] == [], f"{len(problems)} invalid claims"


def test_claim_ids_are_unique_within_a_batch(all_claims):
    for name, claims in all_claims.items():
        dupes = [k for k, v in Counter(c["id"] for c in claims).items() if v > 1]
        assert not dupes, f"{name}: duplicate claim ids {dupes[:3]}"


def test_no_duplicate_object_ids_inside_a_batch(all_claims):
    for name, claims in all_claims.items():
        ids = [c["payload"]["id"] for c in claims
               if c["kind"] in ("assert_object", "candidate_concept")]
        dupes = [k for k, v in Counter(ids).items() if v > 1]
        assert not dupes, f"{name}: duplicate object ids {dupes[:3]}"


def test_every_link_endpoint_resolves_inside_the_seed(all_claims):
    ids = {c["payload"]["id"] for claims in all_claims.values() for c in claims
           if c["kind"] in ("assert_object", "candidate_concept")}
    dangling = []
    for name, claims in all_claims.items():
        for c in claims:
            if c["kind"] == "assert_link":
                if c["subject"] not in ids:
                    dangling.append(f"{name}: subject {c['subject']}")
                if c["object"] not in ids:
                    dangling.append(f"{name}: object {c['object']}")
    assert dangling[:5] == [], f"{len(dangling)} dangling link endpoints"


def test_ids_follow_the_contract_prefixes(all_claims):
    for claims in all_claims.values():
        for c in claims:
            if c["kind"] in ("assert_object", "candidate_concept"):
                oid = c["payload"]["id"]
                assert oid.startswith("trace:"), oid
                assert oid.split(":")[1] in C.TRACE_TYPES, oid
                assert oid == oid.lower(), oid


def test_porb_budget_is_an_attribute_never_a_link(all_claims):
    """Money boundary: HLO budgets live on the HLO object; no link may carry them."""
    hlo_budgets = 0
    for claims in all_claims.values():
        for c in claims:
            if c["kind"] == "assert_object" and c["payload"]["type"] == "hlo":
                assert "budget_usd" in c["payload"]["attrs"], c["payload"]["id"]
                hlo_budgets += 1
            if c["kind"] == "assert_link":
                attrs = c["payload"].get("attrs", {})
                assert c["predicate"] != "BUDGETED"
                assert "budget_usd" not in attrs or c["predicate"] == "WITH_PARTNER", \
                    f"{c['predicate']} carries a budget: {c['payload']['id']}"
                assert "hlo_budget_usd" not in attrs
    assert hlo_budgets >= 1


def test_link_predicates_are_in_the_contract(all_claims):
    for claims in all_claims.values():
        for c in claims:
            if c["kind"] == "assert_link":
                assert c["predicate"] in C.PREDICATES


def test_provenance_and_attestation_of_every_claim(all_claims):
    channels = set()
    for claims in all_claims.values():
        for c in claims:
            assert c["provenance"] == "harvested"
            assert c["attested_by"].startswith("ingest:")
            channels.add(c["attested_by"].split(":")[1].split("@")[0])
    assert channels == set(C.CHANNELS)


def test_heuristic_links_are_banded_medium_and_labelled(all_claims):
    heuristics = [c for claims in all_claims.values() for c in claims
                  if c["kind"] == "assert_link"
                  and str(c["payload"].get("attrs", {}).get("mapping", "")).endswith("heuristic")]
    assert heuristics, "expected the documented result->HLO / HLO->outcome heuristics"
    for c in heuristics:
        assert c["qa"]["band"] == "medium"
        assert c["payload"]["attrs"].get("rule")


def test_taxonomy_claims_carry_a_version(all_claims):
    tagged = [c for c in all_claims["seed-taxonomy.jsonl"] if c["predicate"] == "TAGGED_WITH"]
    assert tagged
    for c in tagged:
        assert c["taxonomy_version"], c["id"]
        assert set(("matched_text", "via", "layer")) <= set(c["payload"]["attrs"])


def test_prms_cgspace_bridge_exists(all_claims):
    same_as = [c for c in all_claims["seed-prms.jsonl"] if c["predicate"] == "SAME_AS"]
    assert len(same_as) >= 5
    for c in same_as:
        assert c["subject"].startswith("trace:result:") and c["object"].startswith("trace:kp:")


def test_seed_extracts_exist_and_are_public():
    for name in ("prms_sp01_results.json", "cgspace_sp01_items.json", "porb_sp01.json",
                 "toc_sp01.json", "taxonomy_v0.2.0.json"):
        p = SEED_DIR / name
        assert p.exists(), p
        data = json.loads(p.read_text(encoding="utf-8"))
        assert isinstance(data, dict) and data

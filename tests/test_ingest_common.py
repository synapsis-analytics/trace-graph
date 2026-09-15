"""WP-D: unit tests for the shared claim builders (ingest/common.py)."""
from __future__ import annotations

import os

os.environ.setdefault("TRACE_INGEST_NOW", "2026-09-15T20:00:00Z")

import pytest  # noqa: E402

from ingest import common as C  # noqa: E402


def test_make_id_shape_and_stability():
    a = C.make_id("result", "prms-24338")
    assert a == "trace:result:prms-24338"
    assert a == C.make_id("result", "PRMS-24338")  # case-insensitive, stable
    assert C.make_id("country", "KE") == "trace:country:ke"
    with pytest.raises(ValueError):
        C.make_id("not_a_type", "x")
    with pytest.raises(ValueError):
        C.make_id("result", "   ")


def test_slugify_and_sha1_12():
    assert C.slugify("Côte d'Ivoire — Market Intelligence!") == "cote-d-ivoire-market-intelligence"
    assert C.slugify("") == "unknown"
    assert C.sha1_12("abc") == C.sha1_12("abc") and len(C.sha1_12("abc")) == 12


def test_canonical_json_is_sorted_and_stable():
    assert C.canonical_json({"b": 1, "a": [2, {"d": 4, "c": 3}]}) == '{"a":[2,{"c":3,"d":4}],"b":1}'


def _obj(**kw):
    return C.object_claim("program", "trace:program:sp01", "Breeding for Tomorrow",
                          channel="prms", system="prms", ref="clarisa_initiatives.id=50",
                          snapshot="prdb_20260913", attrs={"code": "SP01"}, **kw)


def test_object_claim_contract_fields():
    c = _obj()
    assert C.validate_claim(c) == []
    assert c["kind"] == "assert_object"
    assert c["attested_by"] == "ingest:prms@synapsis"
    assert c["provenance"] == "harvested"
    assert set(c["source"]) == {"system", "ref", "snapshot"}
    assert c["payload"]["id"] == "trace:program:sp01"
    assert c["created_at"].endswith("Z")
    assert c["id"].startswith("clm_") and len(c["id"]) == 30  # clm_ + 26 chars


def test_claim_ids_are_deterministic_for_the_same_input():
    """Same input → same ids: the whole point of a reproducible seed."""
    assert _obj()["id"] == _obj()["id"]
    a = C.link_claim("trace:result:prms-1", "WITH_PARTNER", "trace:institution:clarisa-5",
                     channel="prms", system="prms", ref="r", snapshot="s")
    b = C.link_claim("trace:result:prms-1", "WITH_PARTNER", "trace:institution:clarisa-5",
                     channel="prms", system="prms", ref="r", snapshot="s")
    assert a["id"] == b["id"] and a["payload"]["id"] == b["payload"]["id"]
    c = C.link_claim("trace:result:prms-1", "WITH_PARTNER", "trace:institution:clarisa-6",
                     channel="prms", system="prms", ref="r", snapshot="s")
    assert c["id"] != a["id"]


def test_link_claim_carries_predicate_and_claim_id():
    c = C.link_claim("trace:result:prms-1", "LOCATED_IN", "trace:country:ke", channel="prms",
                     system="prms", ref="result_country.result_id=1", snapshot="s",
                     attrs={"kind": "country"})
    assert C.validate_claim(c) == []
    assert c["payload"]["claim_id"] == c["id"]
    assert c["payload"]["id"].startswith("lnk_")
    assert c["predicate"] == "LOCATED_IN" and c["object"] == "trace:country:ke"


def test_unknown_predicate_and_kind_rejected():
    with pytest.raises(ValueError):
        C.link_claim("a", "FRIENDS_WITH", "b", channel="prms", system="p", ref="r", snapshot="s")


def test_attr_and_candidate_claims():
    a = C.attr_claim("trace:result:prms-1", {"year": 2025}, channel="prms", system="prms",
                     ref="r", snapshot="s")
    assert C.validate_claim(a) == [] and a["kind"] == "assert_attr"
    c = C.candidate_concept_claim("market segment", channel="taxonomy", system="taxonomy",
                                  ref="r", snapshot="s", count=7, contexts=["a", "b"],
                                  taxonomy_version="v0.2.0")
    assert C.validate_claim(c) == []
    assert c["kind"] == "candidate_concept" and c["payload"]["attrs"]["hits"] == 7
    assert c["taxonomy_version"] == "v0.2.0"


def test_invalid_claim_is_reported_not_written(tmp_path):
    bad = _obj()
    bad["kind"] = "nonsense"
    with pytest.raises(ValueError):
        C.write_batch(tmp_path / "b.jsonl", [bad])


def test_write_and_read_batch_roundtrip(tmp_path):
    claims = [_obj(), C.link_claim("trace:program:sp01", "PART_OF", "trace:program:sp01",
                                   channel="prms", system="prms", ref="r", snapshot="s")]
    p = tmp_path / "b.jsonl"
    assert C.write_batch(p, claims) == 2
    assert [c["id"] for c in C.read_batch(p)] == [c["id"] for c in claims]


def test_dedupe_helpers():
    a, b = _obj(), _obj()
    assert len(C.dedupe_objects([a, b])) == 1
    l1 = C.link_claim("x", "PART_OF", "y", channel="prms", system="p", ref="1", snapshot="s")
    l2 = C.link_claim("x", "PART_OF", "y", channel="prms", system="p", ref="2", snapshot="s")
    assert len(C.dedupe_links([l1, l2])) == 1


def test_trim_limits_free_text():
    assert C.trim("x" * 5000, 2000) is not None and len(C.trim("x" * 5000, 2000)) == 2000
    assert C.trim("  a\n b ") == "a b"
    assert C.trim(None) is None


@pytest.mark.parametrize("name,iso2", [
    ("Kenya", "KE"), ("Côte d'Ivoire", "CI"), ("The Democratic Republic of the Congo", "CD"),
    ("Tanzania, United Republic", "TZ"), ("Viet Nam", "VN"), ("Global", None),
    ("Regional", None), ("", None), (None, None),
])
def test_country_iso2(name, iso2):
    assert C.country_iso2(name) == iso2


def test_institution_matcher():
    m = C.InstitutionMatcher([
        {"clarisa_id": 50, "name": "International Maize and Wheat Improvement Center",
         "acronym": "CIMMYT"},
        {"clarisa_id": 45, "name": "International Institute of Tropical Agriculture",
         "acronym": "IITA"},
    ])
    assert m.match("CIMMYT")["clarisa_id"] == 50
    assert m.match("international maize and wheat improvement center")["clarisa_id"] == 50
    assert m.match("IITA (Nigeria)")["clarisa_id"] == 45
    assert m.match("Some Unknown NGO") is None
    assert m.match(None) is None

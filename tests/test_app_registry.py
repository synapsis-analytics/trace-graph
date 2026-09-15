"""Registry: append, dry-run, materialisation, supersede, retract, rebuild idempotence."""
from __future__ import annotations

import json

import pytest

from app.db import connect
from app.ids import resolve_alt_id
from app.qa import QAContext
from app.registry import append_claim, counts, decide, get_claim, list_claims, load_batch, rebuild
from tests.conftest import FIXTURE_BATCH, IDS


def test_load_batch_counts(seeded):
    assert seeded["claims"] == 58
    assert seeded["errors"] == []
    assert seeded["accepted"] >= 50


def test_objects_and_links_materialised(seeded):
    c = counts()
    assert c["objects"] == 23        # the fuzzy-duplicate institution stays in review
    assert c["links"] >= 25
    assert c["claims"] == 58


def test_dry_run_does_not_store(seeded):
    before = counts()["claims"]
    out = append_claim(
        {"kind": "assert_object", "subject": "trace:country:ug",
         "payload": {"type": "country", "label": "Uganda", "attrs": {}}},
        dry_run=True,
    )
    assert out["materialised"] is False and out["dry_run"] is True
    assert out["qa"]["status"] == "accepted"
    assert counts()["claims"] == before


def test_append_object_creates_alt_id(seeded):
    append_claim({"kind": "assert_object", "subject": "trace:country:ug",
                  "payload": {"type": "country", "label": "Uganda",
                              "alt_ids": [{"scheme": "iso2", "value": "ug"}]}})
    assert resolve_alt_id("iso2", "UG") == "trace:country:ug"


def test_assert_attr_merges_attributes(seeded):
    hlo_before = _attrs(IDS["hlo"])
    assert hlo_before["budget_usd"] == 71200          # fixture correction applied
    append_claim({"kind": "assert_attr", "subject": IDS["hlo"],
                  "payload": {"attrs": {"assumption": "seed systems stay functional"}},
                  "provenance": "recorded"})
    after = _attrs(IDS["hlo"])
    assert after["budget_usd"] == 71200 and after["assumption"].startswith("seed systems")


def test_retract_removed_the_implausible_country_link(seeded):
    with connect(readonly=True) as conn:
        rows = conn.execute(
            "SELECT * FROM links WHERE object='trace:country:br'").fetchall()
    assert rows == []


def test_supersede_marks_the_old_claim(seeded):
    old = get_claim("clm_FIXTUREGEO1")
    assert old["status"] == "superseded"
    assert "clm_FIXTURERETR1" in old["superseded_by"]


def test_supersede_chain_is_visible(seeded):
    new = get_claim("clm_FIXTURERETR1")
    assert new["supersedes"] == "clm_FIXTUREGEO1"
    assert new["supersede_chain"] == ["clm_FIXTUREGEO1"]


def test_rebuild_is_idempotent(seeded):
    first = rebuild()
    second = rebuild()
    assert first == second
    assert first["objects"] == counts()["objects"]
    assert first["links"] == counts()["links"]


def test_reload_same_batch_creates_no_new_objects(seeded):
    before = counts()
    summary = load_batch(FIXTURE_BATCH)
    after = counts()
    assert summary["errors"] == []                   # explicit claim ids re-load as no-ops
    assert after["objects"] == before["objects"]
    assert after["links"] == before["links"]
    assert after["claims"] > before["claims"]        # the log grows, the graph does not


def test_decide_accept_materialises_a_review_claim(seeded):
    review = [c for c in list_claims(status="review", limit=50)["items"]
              if c["kind"] == "assert_object"][0]
    decide(review["id"], "accept", by="person:test", note="verified by hand")
    stored = get_claim(review["id"])
    assert stored["status"] == "accepted" and stored["decided_by"] == "person:test"
    with connect(readonly=True) as conn:
        assert conn.execute("SELECT 1 FROM objects WHERE id=?", (review["subject"],)).fetchone()


def test_decide_reject_removes_it_again(seeded):
    review = [c for c in list_claims(status="review", limit=50)["items"]
              if c["kind"] == "assert_object"][0]
    decide(review["id"], "accept", by="person:test")
    decide(review["id"], "reject", by="person:test", note="same as KALRO")
    with connect(readonly=True) as conn:
        assert conn.execute("SELECT 1 FROM objects WHERE id=?", (review["subject"],)).fetchone() is None


def test_claims_are_never_deleted(seeded):
    ids = {c["id"] for c in list_claims(limit=200)["items"]}
    rebuild()
    assert {c["id"] for c in list_claims(limit=200)["items"]} == ids


def test_batch_context_resolves_ids_created_in_the_same_batch(clean_db):
    ctx = QAContext()
    a = append_claim({"kind": "assert_object", "subject": "trace:program:sp09",
                      "payload": {"type": "program", "label": "Sustainable Farming"}}, ctx=ctx)
    b = append_claim({"kind": "assert_object", "subject": "trace:aow:sp09-aow02",
                      "payload": {"type": "aow", "label": "Agronomy"}}, ctx=ctx)
    link = append_claim({"kind": "assert_link", "subject": "trace:aow:sp09-aow02",
                         "predicate": "PART_OF", "object": "trace:program:sp09"}, ctx=ctx)
    assert a["status"] == b["status"] == link["status"] == "accepted"


def test_signed_claim_scores_higher_than_harvested(clean_db):
    base = {"kind": "assert_object", "subject": "trace:country:ke",
            "payload": {"type": "country", "label": "Kenya"}}
    harvested = append_claim({**base, "provenance": "harvested"}, dry_run=True)
    signed = append_claim({**base, "provenance": "signed"}, dry_run=True)
    assert signed["qa"]["score"] > harvested["qa"]["score"]


def test_signature_roundtrip(clean_db):
    from app.signing import register_agent, verify

    register_agent("partner:demo-ngo", "Demo NGO", "s3cret", kind="partner")
    claim = append_claim({"kind": "assert_object", "subject": "trace:country:tz",
                          "payload": {"type": "country", "label": "Tanzania"},
                          "attested_by": "partner:demo-ngo"}, sign_with="s3cret")
    assert claim["provenance"] == "signed"
    stored = get_claim(claim["id"])
    assert verify(stored, "s3cret") and not verify(stored, "wrong")


def test_unknown_claim_decision_raises(seeded):
    from app.registry import RegistryError

    with pytest.raises(RegistryError):
        decide("clm_DOESNOTEXIST", "accept")


def _attrs(object_id: str) -> dict:
    with connect(readonly=True) as conn:
        row = conn.execute("SELECT attrs_json FROM objects WHERE id=?", (object_id,)).fetchone()
    return json.loads(row["attrs_json"])

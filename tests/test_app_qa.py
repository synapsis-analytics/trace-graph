"""QA engine: bands, checks, duplicate detection, geo/time plausibility, editable weights."""
from __future__ import annotations

from app.qa import QAContext, load_rules, rerun_all, run_qa
from app.registry import append_claim
from tests.conftest import IDS


def _named(qa, name):
    return next(c for c in qa["checks"] if c["name"] == name)


def test_clean_object_claim_is_accepted(clean_db):
    qa = run_qa({"kind": "assert_object", "subject": IDS["country"],
                 "payload": {"type": "country", "label": "Kenya"}, "provenance": "signed"})
    assert qa["band"] == "high" and qa["status"] == "accepted" and qa["score"] == 1.0


def test_unknown_predicate_is_rejected(clean_db):
    qa = run_qa({"kind": "assert_link", "subject": IDS["result"], "predicate": "INVENTED_BY",
                 "object": IDS["institution"]})
    assert qa["status"] == "rejected"
    assert not _named(qa, "well_formed")["ok"]


def test_predicate_type_fit_is_checked(clean_db):
    qa = run_qa({"kind": "assert_link", "subject": IDS["country"], "predicate": "PART_OF",
                 "object": IDS["program"]})
    assert not _named(qa, "well_formed")["ok"]
    assert "not allowed from type country" in _named(qa, "well_formed")["note"]


def test_malformed_id_fails_well_formed(clean_db):
    qa = run_qa({"kind": "assert_object", "subject": "result-24338",
                 "payload": {"type": "result", "label": "x"}})
    assert not _named(qa, "well_formed")["ok"]


def test_id_resolvable_flags_missing_endpoints(clean_db):
    qa = run_qa({"kind": "assert_link", "subject": IDS["result"], "predicate": "PRODUCED_BY",
                 "object": IDS["institution"]})
    assert not _named(qa, "id_resolvable")["ok"]
    assert qa["status"] in ("review", "rejected")


def test_batch_ids_count_as_resolvable(clean_db):
    ctx = QAContext(batch_ids={IDS["result"], IDS["institution"]})
    qa = run_qa({"kind": "assert_link", "subject": IDS["result"], "predicate": "PRODUCED_BY",
                 "object": IDS["institution"]}, ctx)
    assert _named(qa, "id_resolvable")["ok"]


def test_exact_alt_id_clash_suggests_same_as(seeded):
    qa = run_qa({"kind": "assert_object", "subject": "trace:kp:hdl-10568-999999",
                 "payload": {"type": "kp", "label": "Some other item",
                             "alt_ids": [{"scheme": "cgspace_handle", "value": "10568/175922"}]}})
    dup = _named(qa, "duplicate")
    assert not dup["ok"] and "SAME_AS" in dup["note"]


def test_fuzzy_duplicate_lands_in_review(seeded):
    qa = run_qa({"kind": "assert_object", "subject": "trace:institution:clarisa-4321",
                 "payload": {"type": "institution",
                             "label": "Kenya Agricultural and Livestock Research Organization"},
                 "provenance": "signed"})
    assert qa["status"] == "review" and not _named(qa, "duplicate")["ok"]


def test_geo_outside_programme_countries_is_flagged(seeded):
    qa = run_qa({"kind": "assert_link", "subject": IDS["result"], "predicate": "LOCATED_IN",
                 "object": "trace:country:br"})
    assert not _named(qa, "plausible_geo")["ok"]


def test_geo_inside_programme_countries_passes(seeded):
    qa = run_qa({"kind": "assert_link", "subject": IDS["result"], "predicate": "LOCATED_IN",
                 "object": IDS["country"]})
    assert _named(qa, "plausible_geo")["ok"] and qa["status"] == "accepted"


def test_geo_of_non_result_is_source_of_truth(clean_db):
    qa = run_qa({"kind": "assert_link", "subject": IDS["hlo"], "predicate": "LOCATED_IN",
                 "object": "trace:country:ng"})
    assert _named(qa, "plausible_geo")["ok"]


def test_invalid_iso_code_fails_geo(clean_db):
    qa = run_qa({"kind": "assert_link", "subject": IDS["result"], "predicate": "LOCATED_IN",
                 "object": "trace:country:kenya"})
    assert not _named(qa, "plausible_geo")["ok"]


def test_year_outside_range_fails_time(clean_db):
    qa = run_qa({"kind": "assert_object", "subject": IDS["result"],
                 "payload": {"type": "result", "label": "Old result", "attrs": {"year": 1999}}})
    assert not _named(qa, "plausible_time")["ok"]


def test_evidence_link_needs_a_locator(clean_db):
    without = run_qa({"kind": "assert_link", "subject": IDS["result"], "predicate": "EVIDENCED_BY",
                      "object": IDS["kp"]})
    with_ev = run_qa({"kind": "assert_link", "subject": IDS["result"], "predicate": "EVIDENCED_BY",
                      "object": IDS["kp"],
                      "evidence": [{"kind": "handle", "value": "10568/175922"}]})
    assert not _named(without, "evidence_present")["ok"]
    assert _named(with_ev, "evidence_present")["ok"]


def test_taxonomy_resolvable_requires_a_known_concept(seeded):
    ok = run_qa({"kind": "assert_link", "subject": IDS["kp"], "predicate": "TAGGED_WITH",
                 "object": IDS["concept"]})
    missing = run_qa({"kind": "assert_link", "subject": IDS["kp"], "predicate": "TAGGED_WITH",
                      "object": "trace:concept:l2-9999"})
    assert _named(ok, "taxonomy_resolvable")["ok"]
    assert not _named(missing, "taxonomy_resolvable")["ok"]


def test_deprecated_concept_proposes_replacement(clean_db):
    append_claim({"kind": "assert_object", "subject": "trace:concept:l2-0099",
                  "payload": {"type": "concept", "label": "old term",
                              "attrs": {"status": "deprecated", "replaced_by": "L2-0074"}}})
    qa = run_qa({"kind": "assert_link", "subject": IDS["kp"], "predicate": "TAGGED_WITH",
                 "object": "trace:concept:l2-0099"})
    check = _named(qa, "taxonomy_resolvable")
    assert not check["ok"] and "replaced_by=L2-0074" in check["note"]


def test_candidate_concepts_always_go_to_review(clean_db):
    qa = run_qa({"kind": "candidate_concept", "subject": "trace:concept:l1-new-term",
                 "payload": {"term": "new term", "count": 3}, "provenance": "recorded"})
    assert qa["status"] == "review" and qa["band"] == "high"


def test_bands_come_from_the_editable_rules_file():
    rules = load_rules()
    assert rules["bands"]["high"] == 0.85 and rules["bands"]["medium"] == 0.60
    assert set(rules["weights"]) >= {"well_formed", "duplicate", "plausible_geo"}


def test_qa_rerun_rescoring_keeps_every_claim(seeded):
    out = rerun_all()
    assert out["claims"] == 58


def test_retraction_is_not_judged_on_content(seeded):
    qa = run_qa({"kind": "retract", "subject": IDS["result"], "predicate": "LOCATED_IN",
                 "object": "trace:country:br", "provenance": "recorded"})
    assert qa["status"] == "accepted"
    assert _named(qa, "retraction")["ok"]
    assert not any(c["name"] == "plausible_geo" for c in qa["checks"])

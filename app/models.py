"""Pydantic models + the claim JSON Schema (PLAN §3.2-§3.4 CONTRACT)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.ids import ALT_ID_SCHEMES, OBJECT_TYPES

CLAIM_KINDS = ("assert_object", "assert_link", "assert_attr", "retract", "candidate_concept")
PROVENANCE = ("harvested", "recorded", "signed")
STATUSES = ("accepted", "review", "rejected")
BANDS = ("high", "medium", "low")

# predicate -> allowed subject types / object types (PLAN §3.3). "*" = any type.
# The "from" lists are a superset of the PLAN table: the PORB/CGSpace channels legitimately state
# e.g. indicator LOCATED_IN country, aow WITH_PARTNER institution, outcome FUNDED_BY project.
# Shapes that are genuinely meaningless (country PART_OF program, result BROADER concept, …) are
# still rejected by the well_formed check.
PREDICATES: dict[str, dict[str, Any]] = {
    "PART_OF": {"from": ["aow", "hlo", "indicator", "outcome"], "to": ["program", "aow", "hlo"],
                "desc": "results-framework hierarchy"},
    "CONTRIBUTES_TO": {"from": ["result", "innovation", "kp", "hlo", "indicator", "aow", "outcome"], "to": ["hlo", "indicator", "outcome"],
                       "desc": "PRMS ToC / indicator mapping"},
    "REPORTED_UNDER": {"from": ["result", "kp", "innovation", "melia_study", "project"], "to": ["program"], "desc": "reporting initiative"},
    "PRODUCED_BY": {"from": ["result", "kp", "innovation", "document", "melia_study"], "to": ["institution"], "desc": "lead centre"},
    "WITH_PARTNER": {"from": ["result", "hlo", "kp", "aow", "program", "outcome", "project",
                              "indicator", "innovation", "melia_study"], "to": ["institution"], "desc": "partner"},
    "LOCATED_IN": {"from": ["result", "hlo", "project", "melia_study", "kp", "aow", "indicator",
                            "outcome", "institution", "innovation", "program"],
                   "to": ["country", "region"], "desc": "geography"},
    "EVIDENCED_BY": {"from": ["result", "program", "innovation", "hlo", "outcome", "aow",
                              "indicator", "melia_study", "project", "kp"],
                     "to": ["kp", "document"], "desc": "evidence"},
    "SAME_AS": {"from": ["*"], "to": ["*"], "desc": "identity bridge (e.g. PRMS KP result ↔ CGSpace item)"},
    "DESCRIBES": {"from": ["kp", "document", "innovation", "result", "melia_study"], "to": ["innovation", "result"], "desc": "document about a thing"},
    "FUNDED_BY": {"from": ["hlo", "result", "program", "aow", "outcome", "indicator",
                           "melia_study", "innovation"], "to": ["project"], "desc": "PORB W3/bilateral"},
    "STUDIED_BY": {"from": ["outcome", "hlo", "aow", "program", "indicator", "result"], "to": ["melia_study"], "desc": "MELIA study"},
    "SYNERGY_WITH": {"from": ["hlo", "program", "aow"], "to": ["program"], "desc": "synergy programs"},
    "TAGGED_WITH": {"from": ["*"], "to": ["concept"], "desc": "taxonomy tag"},
    "BROADER": {"from": ["concept"], "to": ["concept"], "desc": "taxonomy hierarchy"},
    "CANDIDATE_FOR": {"from": ["concept"], "to": ["concept"], "desc": "reconciliation candidate"},
    "AUTHORED_BY": {"from": ["kp", "document", "result"], "to": ["person"], "desc": "authorship"},
}

# Attribute-boundary rule (D-Jose-c): these attrs never propagate along links.
NON_PROPAGATING_ATTRS = ("budget_usd", "amount_usd", "target", "share_pct")

CLAIM_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "TRACE claim",
    "type": "object",
    "required": ["kind"],
    "additionalProperties": True,
    "properties": {
        "id": {"type": "string", "pattern": "^clm_[A-Za-z0-9]+$"},
        "kind": {"type": "string", "enum": list(CLAIM_KINDS)},
        "subject": {"type": ["string", "null"]},
        "predicate": {"type": ["string", "null"]},
        "object": {"type": ["string", "null"]},
        "payload": {"type": "object"},
        "attested_by": {"type": ["string", "null"]},
        "provenance": {"type": ["string", "null"], "enum": list(PROVENANCE) + [None]},
        "signature": {"type": ["string", "null"]},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["kind", "value"],
                "properties": {
                    "kind": {"type": "string", "enum": ["url", "handle", "doi", "file", "text"]},
                    "value": {"type": "string"},
                },
                "additionalProperties": True,
            },
        },
        "taxonomy_version": {"type": ["string", "null"]},
        "source": {"type": "object"},
        "created_at": {"type": ["string", "null"]},
        "supersedes": {"type": ["string", "null"]},
        "qa": {"type": "object"},
    },
    "allOf": [
        {
            "if": {"properties": {"kind": {"const": "assert_object"}}, "required": ["kind"]},
            "then": {"required": ["subject", "payload"]},
        },
        {
            "if": {"properties": {"kind": {"const": "assert_link"}}, "required": ["kind"]},
            "then": {"required": ["subject", "predicate", "object"]},
        },
        {
            "if": {"properties": {"kind": {"const": "assert_attr"}}, "required": ["kind"]},
            "then": {"required": ["subject", "payload"]},
        },
        {
            "if": {"properties": {"kind": {"const": "retract"}}, "required": ["kind"]},
            "then": {"required": ["subject"]},
        },
    ],
}


class AltId(BaseModel):
    scheme: str
    value: str


class ObjectPayload(BaseModel):
    type: str
    label: str = ""
    description: str = ""
    attrs: dict[str, Any] = Field(default_factory=dict)
    alt_ids: list[AltId] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)


class ClaimIn(BaseModel):
    """Inbound claim body for POST /api/claims (ids/timestamps are assigned server side)."""

    id: str | None = None
    kind: Literal["assert_object", "assert_link", "assert_attr", "retract", "candidate_concept"]
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    attested_by: str | None = "agent:anonymous"
    provenance: Literal["harvested", "recorded", "signed"] | None = "recorded"
    signature: str | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    taxonomy_version: str | None = None
    source: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    supersedes: str | None = None

    model_config = {"extra": "allow"}


class DecisionIn(BaseModel):
    decision: Literal["accept", "reject"]
    by: str = "person:unknown"
    note: str = ""


class TagIn(BaseModel):
    object_ids: list[str] | None = None
    text: str | None = None


class AskIn(BaseModel):
    question: str


class PublishIn(BaseModel):
    bump: Literal["major", "minor", "patch"] = "minor"
    notes: str = ""


class IngestIn(BaseModel):
    limit: int | None = None


def known_types() -> tuple[str, ...]:
    return OBJECT_TYPES


def known_schemes() -> tuple[str, ...]:
    return ALT_ID_SCHEMES

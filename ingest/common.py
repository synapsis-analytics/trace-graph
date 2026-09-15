"""TRACE Graph — shared claim-building helpers for every intake channel.

Implements the CONTRACT in ``analysis/trace-proto-20260915/PLAN.md`` §3.1–§3.4:
identifiers, object/link/attr/candidate claims, canonical JSON and the JSON-Schema
that every emitted claim must satisfy.

Design notes (assumptions taken by WP-D, documented in data/seed/SEED-REPORT.md):

* **Claim ids are "ULID-ish" but deterministic.** ``clm_`` / ``lnk_`` + 26 Crockford
  base-32 chars: 10 chars of millisecond timestamp (time-sortable, exactly like a ULID)
  + 16 chars derived from a SHA-1 of the claim content instead of randomness.  This keeps
  the committed seed batches byte-stable across re-runs (so ``trace rebuild`` is
  idempotent and git diffs are meaningful) while remaining a valid 26-char ULID string.
  Set ``TRACE_INGEST_NOW`` to freeze the timestamp part (the CLI does this by default).
* Every claim carries ``attested_by="ingest:<channel>@synapsis"`` and
  ``provenance="harvested"`` — these are harvested facts, not signed attestations (D6).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Sequence

from jsonschema import Draft202012Validator

# --------------------------------------------------------------------------------------
# Controlled vocabularies (CONTRACT §3.2 / §3.3 / §3.4)
# --------------------------------------------------------------------------------------
TRACE_TYPES: tuple[str, ...] = (
    "program", "aow", "hlo", "indicator", "outcome", "result", "kp", "innovation",
    "institution", "country", "region", "project", "melia_study", "concept", "person",
    "document",
)

PREDICATES: tuple[str, ...] = (
    "PART_OF", "CONTRIBUTES_TO", "REPORTED_UNDER", "PRODUCED_BY", "WITH_PARTNER",
    "LOCATED_IN", "EVIDENCED_BY", "SAME_AS", "DESCRIBES", "FUNDED_BY", "STUDIED_BY",
    "SYNERGY_WITH", "TAGGED_WITH", "BROADER", "CANDIDATE_FOR", "SUPERSEDES", "AUTHORED_BY",
)

CLAIM_KINDS: tuple[str, ...] = (
    "assert_object", "assert_link", "assert_attr", "retract", "candidate_concept",
)

CHANNELS: tuple[str, ...] = ("prms", "cgspace", "porb", "toc", "taxonomy")

BANDS = ("high", "medium", "low")

# --------------------------------------------------------------------------------------
# Time
# --------------------------------------------------------------------------------------
_FROZEN_NOW = os.environ.get("TRACE_INGEST_NOW", "").strip() or None


def now_iso() -> str:
    """UTC ISO-8601 timestamp; frozen by ``TRACE_INGEST_NOW`` for reproducible batches."""
    if _FROZEN_NOW:
        return _FROZEN_NOW
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_ms() -> int:
    ts = now_iso()
    try:
        dt = _dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)
    except ValueError:  # pragma: no cover - defensive
        dt = _dt.datetime.now(_dt.timezone.utc)
    return int(dt.timestamp() * 1000)


# --------------------------------------------------------------------------------------
# Identifiers
# --------------------------------------------------------------------------------------
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _b32(value: int, length: int) -> str:
    out = []
    for _ in range(length):
        out.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(out))


def sha1_12(text: str) -> str:
    """First 12 hex chars of the SHA-1 of ``text`` (used in TRACE ids for row-level keys)."""
    return hashlib.sha1(str(text).encode("utf-8")).hexdigest()[:12]


def slugify(text: str, max_len: int = 80) -> str:
    """Lowercase, ASCII, URL-safe slug. Never used for objects whose source key is stable."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    text = re.sub(r"-{2,}", "-", text)
    return text[:max_len].strip("-") or "unknown"


def make_id(otype: str, key: str) -> str:
    """``trace:<type>:<key>`` — key must derive from the *source primary key* (CONTRACT §3.1)."""
    if otype not in TRACE_TYPES:
        raise ValueError(f"unknown object type: {otype}")
    key = str(key).strip().lower()
    key = re.sub(r"[^a-z0-9._:-]+", "-", key).strip("-")
    if not key:
        raise ValueError(f"empty id key for type {otype}")
    return f"trace:{otype}:{key}"


def _ulidish(prefix: str, seed: str) -> str:
    """26-char time-sortable, content-derived id (see module docstring)."""
    ts = _b32(_now_ms() & ((1 << 48) - 1), 10)
    digest = int(hashlib.sha1(seed.encode("utf-8")).hexdigest()[:20], 16)
    return f"{prefix}{ts}{_b32(digest & ((1 << 80) - 1), 16)}"


def claim_id(seed: str) -> str:
    return _ulidish("clm_", "claim|" + seed)


def link_id(subject: str, predicate: str, obj: str, disambiguator: str = "") -> str:
    return _ulidish("lnk_", f"link|{subject}|{predicate}|{obj}|{disambiguator}")


# --------------------------------------------------------------------------------------
# Canonical JSON
# --------------------------------------------------------------------------------------
def canonical_json(obj: Any) -> str:
    """Stable JSON serialisation (sorted keys, compact, unicode preserved)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _clean(value: Any) -> Any:
    """Drop ``None`` values from attr dicts and strip strings, recursively."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items() if v is not None and v != ""}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value if v is not None and v != ""]
    if isinstance(value, str):
        return value.strip()
    return value


def trim(text: Any, limit: int = 2000) -> str | None:
    """Trim free text to ``limit`` chars (PRMS descriptions can be enormous)."""
    if text is None:
        return None
    s = re.sub(r"\s+", " ", str(text)).strip()
    if not s:
        return None
    return s[: limit - 1] + "…" if len(s) > limit else s


# --------------------------------------------------------------------------------------
# Claim schema (CONTRACT §3.4)
# --------------------------------------------------------------------------------------
CLAIM_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "TRACE claim",
    "type": "object",
    "required": [
        "id", "kind", "subject", "payload", "attested_by", "provenance", "evidence",
        "source", "created_at", "supersedes", "qa",
    ],
    "additionalProperties": False,
    "properties": {
        "id": {"type": "string", "pattern": r"^clm_[0-9A-HJKMNP-TV-Z]{26}$"},
        "kind": {"enum": list(CLAIM_KINDS)},
        "subject": {"type": "string", "minLength": 1},
        "predicate": {"type": ["string", "null"], "enum": list(PREDICATES) + [None]},
        "object": {"type": ["string", "null"]},
        "payload": {"type": "object"},
        "attested_by": {"type": "string", "minLength": 1},
        "provenance": {"enum": ["harvested", "recorded", "signed"]},
        "signature": {"type": ["string", "null"]},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["kind", "value"],
                "additionalProperties": False,
                "properties": {
                    "kind": {"enum": ["url", "handle", "doi", "file", "text"]},
                    "value": {"type": "string"},
                },
            },
        },
        "taxonomy_version": {"type": ["string", "null"]},
        "source": {
            "type": "object",
            "required": ["system", "ref", "snapshot"],
            "additionalProperties": False,
            "properties": {
                "system": {"type": "string"},
                "ref": {"type": "string"},
                "snapshot": {"type": "string"},
            },
        },
        "created_at": {"type": "string", "minLength": 10},
        "supersedes": {"type": ["string", "null"]},
        "qa": {
            "type": "object",
            "required": ["band", "score", "checks", "status"],
            "additionalProperties": True,
            "properties": {
                "band": {"enum": list(BANDS) + [None]},
                "score": {"type": ["number", "null"]},
                "checks": {"type": "array"},
                "status": {"enum": ["accepted", "review", "rejected", None]},
                "decided_by": {"type": ["string", "null"]},
                "decided_at": {"type": ["string", "null"]},
            },
        },
    },
    "allOf": [
        {
            "if": {"properties": {"kind": {"const": "assert_link"}}},
            "then": {"required": ["predicate", "object"],
                     "properties": {"predicate": {"type": "string"},
                                    "object": {"type": "string", "minLength": 1}}},
        },
        {
            "if": {"properties": {"kind": {"const": "assert_object"}}},
            "then": {"properties": {"payload": {"required": ["id", "type", "label"]}}},
        },
    ],
}

_VALIDATOR = Draft202012Validator(CLAIM_SCHEMA)


def validate_claim(claim: dict[str, Any]) -> list[str]:
    """Return a list of human-readable schema errors (empty == valid)."""
    return [
        f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in _VALIDATOR.iter_errors(claim)
    ]


# --------------------------------------------------------------------------------------
# Claim builders
# --------------------------------------------------------------------------------------
def _qa(band: str | None = None, note: str | None = None) -> dict[str, Any]:
    qa: dict[str, Any] = {
        "band": band, "score": None, "checks": [], "status": None,
        "decided_by": None, "decided_at": None,
    }
    if note:
        qa["ingest_note"] = note
    return qa


def _source(system: str, ref: str, snapshot: str) -> dict[str, str]:
    return {"system": system, "ref": str(ref), "snapshot": snapshot}


def _base_claim(
    kind: str,
    subject: str,
    payload: dict[str, Any],
    *,
    channel: str,
    system: str,
    ref: str,
    snapshot: str,
    predicate: str | None = None,
    obj: str | None = None,
    evidence: Sequence[dict[str, str]] | None = None,
    taxonomy_version: str | None = None,
    band: str | None = None,
    note: str | None = None,
    seed: str | None = None,
) -> dict[str, Any]:
    if kind not in CLAIM_KINDS:
        raise ValueError(f"unknown claim kind: {kind}")
    if predicate is not None and predicate not in PREDICATES:
        raise ValueError(f"unknown predicate: {predicate}")
    payload = _clean(payload)
    seed = seed or canonical_json([kind, subject, predicate, obj, payload, system, ref])
    claim = {
        "id": claim_id(seed),
        "kind": kind,
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "payload": payload,
        "attested_by": f"ingest:{channel}@synapsis",
        "provenance": "harvested",
        "signature": None,
        "evidence": [dict(e) for e in (evidence or [])],
        "taxonomy_version": taxonomy_version,
        "source": _source(system, ref, snapshot),
        "created_at": now_iso(),
        "supersedes": None,
        "qa": _qa(band, note),
    }
    return claim


def object_claim(
    otype: str,
    oid: str,
    label: str,
    *,
    channel: str,
    system: str,
    ref: str,
    snapshot: str,
    description: str | None = None,
    attrs: dict[str, Any] | None = None,
    alt_ids: Iterable[dict[str, str]] | None = None,
    evidence: Sequence[dict[str, str]] | None = None,
    taxonomy_version: str | None = None,
    band: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """``assert_object`` claim — payload is the object body of CONTRACT §3.2."""
    if otype not in TRACE_TYPES:
        raise ValueError(f"unknown object type: {otype}")
    ts = now_iso()
    payload = {
        "id": oid,
        "type": otype,
        "label": trim(label, 500) or oid,
        "description": trim(description, 2000),
        "attrs": _clean(attrs or {}),
        "alt_ids": [dict(a) for a in (alt_ids or [])],
        "source": _source(system, ref, snapshot),
        "created_at": ts,
        "updated_at": ts,
    }
    return _base_claim(
        "assert_object", oid, payload, channel=channel, system=system, ref=ref,
        snapshot=snapshot, evidence=evidence, taxonomy_version=taxonomy_version,
        band=band, note=note, seed=f"object|{oid}|{system}|{ref}",
    )


def link_claim(
    subject: str,
    predicate: str,
    obj: str,
    *,
    channel: str,
    system: str,
    ref: str,
    snapshot: str,
    attrs: dict[str, Any] | None = None,
    evidence: Sequence[dict[str, str]] | None = None,
    taxonomy_version: str | None = None,
    band: str | None = None,
    note: str | None = None,
    disambiguator: str = "",
) -> dict[str, Any]:
    """``assert_link`` claim — payload is the link body of CONTRACT §3.3."""
    cid = claim_id(f"link|{subject}|{predicate}|{obj}|{disambiguator}|{system}|{ref}")
    payload = {
        "id": link_id(subject, predicate, obj, disambiguator),
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "attrs": _clean(attrs or {}),
        "claim_id": cid,
    }
    claim = _base_claim(
        "assert_link", subject, payload, channel=channel, system=system, ref=ref,
        snapshot=snapshot, predicate=predicate, obj=obj, evidence=evidence,
        taxonomy_version=taxonomy_version, band=band, note=note,
        seed=f"link|{subject}|{predicate}|{obj}|{disambiguator}|{system}|{ref}",
    )
    claim["id"] = cid
    return claim


def attr_claim(
    subject: str,
    attrs: dict[str, Any],
    *,
    channel: str,
    system: str,
    ref: str,
    snapshot: str,
    evidence: Sequence[dict[str, str]] | None = None,
    band: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """``assert_attr`` claim — adds/updates attributes on an existing object."""
    return _base_claim(
        "assert_attr", subject, {"attrs": _clean(attrs)}, channel=channel, system=system,
        ref=ref, snapshot=snapshot, evidence=evidence, band=band, note=note,
        seed=f"attr|{subject}|{canonical_json(_clean(attrs))}|{ref}",
    )


def candidate_concept_claim(
    term: str,
    *,
    channel: str,
    system: str,
    ref: str,
    snapshot: str,
    count: int = 1,
    contexts: Sequence[str] | None = None,
    taxonomy_version: str | None = None,
    suggested_layer: int = 2,
    band: str | None = "medium",
) -> dict[str, Any]:
    """``candidate_concept`` claim — a frequent free term with no L2/L3 match (Jules' loop).

    The payload is a normal ``concept`` object (a type the CONTRACT knows) living in the
    ``cand-`` id namespace and flagged ``attrs.candidate = true`` / ``attrs.status = "proposed"``,
    so the QA gate can route it to the review queue by *claim kind* without having to learn a new
    object type. It is deliberately **not** a Layer-2/3 term until the taxonomy steering group
    says so.
    """
    cid = make_id("concept", "cand-" + slugify(term))
    payload = {
        "id": cid,
        "type": "concept",
        "label": trim(term, 200),
        "attrs": {
            "term": trim(term, 200),
            "candidate": True,
            "hits": count,
            "layer": None,
            "suggested_layer": suggested_layer,
            "contexts": [trim(c, 240) for c in (contexts or [])][:5],
            "status": "proposed",
        },
        "alt_ids": [],
    }
    return _base_claim(
        "candidate_concept", cid, payload, channel=channel, system=system, ref=ref,
        snapshot=snapshot, taxonomy_version=taxonomy_version, band=band,
        seed=f"candidate|{cid}|{system}",
    )


# --------------------------------------------------------------------------------------
# Batch IO
# --------------------------------------------------------------------------------------
def write_batch(path: str | os.PathLike[str], claims: Iterable[dict[str, Any]],
                validate: bool = True) -> int:
    """Write claims as JSON-Lines (canonical JSON, one claim per line). Returns the count."""
    claims = list(claims)
    if validate:
        problems: list[str] = []
        for c in claims:
            for err in validate_claim(c):
                problems.append(f"{c.get('id')} [{c.get('kind')}] {err}")
        if problems:
            raise ValueError(
                f"{len(problems)} invalid claim(s); first 5:\n  " + "\n  ".join(problems[:5])
            )
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        for c in claims:
            fh.write(canonical_json(c) + "\n")
    return len(claims)


def read_batch(path: str | os.PathLike[str]) -> list[dict[str, Any]]:
    out = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def write_extract(path: str | os.PathLike[str], data: Any) -> None:
    """Vendored public input extract (pretty JSON so it reads well on GitHub)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False, sort_keys=False) + "\n",
                 encoding="utf-8")


def summarise(claims: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Counts by kind / object type / predicate — used by the CLI summary table."""
    from collections import Counter
    kinds, types_, preds = Counter(), Counter(), Counter()
    for c in claims:
        kinds[c["kind"]] += 1
        if c["kind"] in ("assert_object", "candidate_concept"):
            types_[c["payload"].get("type", "?")] += 1
        elif c["kind"] == "assert_link":
            preds[c["predicate"]] += 1
    return {"total": len(claims), "kinds": dict(kinds), "objects": dict(types_),
            "links": dict(preds)}


def dedupe_objects(claims: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the first ``assert_object`` per id inside a batch (QA duplicate rule §3.5)."""
    seen: set[str] = set()
    out = []
    for c in claims:
        if c["kind"] == "assert_object":
            oid = c["payload"]["id"]
            if oid in seen:
                continue
            seen.add(oid)
        out.append(c)
    return out


def dedupe_links(claims: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the first link per (subject, predicate, object) triple inside a batch."""
    seen: set[tuple[str, str, str]] = set()
    out = []
    for c in claims:
        if c["kind"] == "assert_link":
            key = (c["subject"], c["predicate"] or "", c["object"] or "")
            if key in seen:
                continue
            seen.add(key)
        out.append(c)
    return out


# --------------------------------------------------------------------------------------
# Country / institution resolution helpers (shared by the PORB and CGSpace channels)
# --------------------------------------------------------------------------------------
#: Names used in the PORB workbook / CGSpace metadata that pycountry does not resolve.
COUNTRY_ALIASES: dict[str, str] = {
    "cote d ivoire": "CI", "cote divoire": "CI", "ivory coast": "CI",
    "the democratic republic of the congo": "CD", "democratic republic of the congo": "CD",
    "dr congo": "CD", "drc": "CD", "congo democratic republic": "CD",
    "republic of the congo": "CG", "congo": "CG",
    "tanzania": "TZ", "tanzania united republic": "TZ", "united republic of tanzania": "TZ",
    "bolivia": "BO", "venezuela": "VE", "iran": "IR", "syria": "SY", "laos": "LA",
    "vietnam": "VN", "viet nam": "VN", "the socialist republic of viet nam": "VN",
    "socialist republic of viet nam": "VN", "south korea": "KR", "north korea": "KP",
    "the republic of the sudan": "SD", "sudan": "SD", "south sudan": "SS",
    "the united republic of tanzania": "TZ", "lao pdr": "LA", "ivory coast republic": "CI",
    "moldova": "MD", "russia": "RU", "turkey": "TR", "turkiye": "TR",
    "cape verde": "CV", "swaziland": "SZ", "eswatini": "SZ", "burma": "MM", "myanmar": "MM",
    "palestine": "PS", "west bank and gaza": "PS", "usa": "US", "united states": "US",
    "uk": "GB", "united kingdom": "GB", "gambia": "GM", "the gambia": "GM",
    "philippines": "PH", "the philippines": "PH", "netherlands": "NL",
}

#: Values that are *not* countries — mapped to regions or skipped (documented in SEED-REPORT).
NON_COUNTRY_GEO = {
    "global", "regional", "worldwide", "multiple", "n/a", "na", "tbd", "various",
}


def country_iso2(name: str | None) -> str | None:
    """Best-effort country name → ISO-3166 alpha-2, or ``None`` (regions/Global included)."""
    if not name:
        return None
    raw = str(name).replace("\xa0", " ").strip()
    if not raw:
        return None
    key = re.sub(r"[^a-z ]+", " ", unicodedata.normalize("NFKD", raw)
                 .encode("ascii", "ignore").decode("ascii").lower())
    key = re.sub(r"\s+", " ", key).strip()
    if key in NON_COUNTRY_GEO:
        return None
    if key in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[key]
    try:
        import pycountry
    except ImportError:  # pragma: no cover
        return None
    hit = pycountry.countries.get(name=raw) or pycountry.countries.get(common_name=raw)
    if hit is None and len(raw) == 2:
        hit = pycountry.countries.get(alpha_2=raw.upper())
    if hit is None:
        try:
            matches = pycountry.countries.search_fuzzy(raw)
            hit = matches[0] if matches else None
        except LookupError:
            hit = None
    return hit.alpha_2 if hit else None


def country_name(iso2: str) -> str:
    try:
        import pycountry
        hit = pycountry.countries.get(alpha_2=iso2.upper())
        return getattr(hit, "common_name", None) or hit.name if hit else iso2
    except Exception:  # pragma: no cover
        return iso2


class InstitutionMatcher:
    """Match free-text organisation names to CLARISA institutions seen in the PRMS extract.

    Deliberately conservative (exact normalised name, acronym, or a contained-acronym hit) —
    the QA engine, not the ingest script, is where fuzzy duplicates get adjudicated.
    """

    def __init__(self, institutions: Iterable[dict[str, Any]] = ()):  # noqa: D107
        self.by_name: dict[str, dict[str, Any]] = {}
        self.by_acronym: dict[str, dict[str, Any]] = {}
        for inst in institutions:
            self.add(inst)

    @staticmethod
    def _norm(text: str) -> str:
        text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
        text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
        return re.sub(r"\s+", " ", text).strip()

    def add(self, inst: dict[str, Any]) -> None:
        name = inst.get("name")
        if name:
            self.by_name.setdefault(self._norm(name), inst)
        acr = inst.get("acronym")
        if acr and len(str(acr)) >= 3:
            self.by_acronym.setdefault(self._norm(acr), inst)

    def match(self, name: str | None) -> dict[str, Any] | None:
        if not name:
            return None
        key = self._norm(name)
        if not key:
            return None
        if key in self.by_name:
            return self.by_name[key]
        if key in self.by_acronym:
            return self.by_acronym[key]
        # "CIMMYT (International Maize ...)" style strings
        for token in re.findall(r"\b[a-z]{3,12}\b", key):
            if token in self.by_acronym:
                return self.by_acronym[token]
        return None


def load_prms_institutions(extract_path: str | os.PathLike[str]) -> list[dict[str, Any]]:
    """Collect the CLARISA institution records vendored in the PRMS extract."""
    p = Path(extract_path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    out: dict[int, dict[str, Any]] = {}
    for r in data.get("results", []):
        for key in ("institutions", "centres"):
            for i in r.get(key) or []:
                if i.get("clarisa_id"):
                    out.setdefault(i["clarisa_id"], i)
    return list(out.values())


# --------------------------------------------------------------------------------------
# API-callable channel entry points (WP-I): POST /api/ingest/{channel} calls
# `ingest.<channel>.run_channel(limit=…)` — keyword-only — and expects a dict summary.
# Batches produced this way are written to data/claims/<channel>-<date>.jsonl (never over the
# committed seed batches) and loaded into the registry through the normal QA gate.

def channel_out_path(channel: str, out: str | os.PathLike[str] | None = None) -> str:
    if out:
        return str(out)
    base = Path(os.getenv("TRACE_DATA_DIR", "data")) / "claims"
    base.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")
    return str(base / f"{channel}-{stamp}.jsonl")


def runtime_extract_path(channel: str) -> str:
    base = Path(os.getenv("TRACE_DATA_DIR", "data")) / "runtime"
    base.mkdir(parents=True, exist_ok=True)
    return str(base / f"{channel}-extract.json")


def load_into_registry(paths: Sequence[str | os.PathLike[str]]) -> list[dict[str, Any]]:
    from app.registry import load_batches  # local import: ingest must not depend on app at import time

    return load_batches([Path(p) for p in paths])


def replay_committed_batches(channel: str) -> dict[str, Any]:
    """Fallback when the upstream source is not available on this machine (e.g. a prod worktree
    with no PRMS snapshot): replay the committed claim batches for the channel."""
    base = Path(os.getenv("TRACE_DATA_DIR", "data")) / "claims"
    batches = sorted(p for p in base.glob(f"*{channel}*.jsonl"))
    if not batches:
        return {"channel": channel, "mode": "replay-batches", "batches": [], "loaded": []}
    return {"channel": channel, "mode": "replay-batches",
            "batches": [str(b) for b in batches], "loaded": load_into_registry(batches)}


def channel_entry(channel: str, builder, load: bool = True) -> dict[str, Any]:
    """Run `builder()` (which must write a batch and return a summary with `out`), then load it."""
    try:
        summary = builder()
    except Exception as exc:  # source missing / unreadable -> honest fallback, never a crash
        out = replay_committed_batches(channel)
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out
    summary.setdefault("channel", channel)
    summary["mode"] = "live-source"
    if load and summary.get("out"):
        summary["loaded"] = load_into_registry([summary["out"]])
    return summary

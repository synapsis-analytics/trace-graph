"""TRACE identifier helpers (PLAN §3.1)."""
from __future__ import annotations

import hashlib
import re
from typing import Iterable

OBJECT_TYPES: tuple[str, ...] = (
    "program", "aow", "hlo", "indicator", "outcome", "result", "kp", "innovation",
    "institution", "country", "region", "project", "melia_study", "concept", "person",
    "document",
)

ALT_ID_SCHEMES: tuple[str, ...] = (
    "prms_result_id", "prms_result_code", "cgspace_handle", "doi", "clarisa_institution_id",
    "iso2", "clarisa_initiative_code", "porb_row", "taxonomy_term_id", "taxonomy_uri",
    "toc_result_id",
)

ID_RE = re.compile(r"^trace:([a-z_]+):([a-z0-9][a-z0-9._-]*)$")
_SLUG_CLEAN = re.compile(r"[^a-z0-9]+")


class InvalidId(ValueError):
    """Raised when a TRACE id does not follow the contract."""


def slugify(value: str, max_len: int = 80) -> str:
    s = _SLUG_CLEAN.sub("-", str(value).strip().lower()).strip("-")
    return (s[:max_len].rstrip("-")) or "x"


def sha1_12(*parts: str) -> str:
    joined = "|".join(str(p).strip() for p in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]


def make_id(type_: str, slug: str) -> str:
    if type_ not in OBJECT_TYPES:
        raise InvalidId(f"unknown object type: {type_}")
    return f"trace:{type_}:{slugify(slug)}"


def parse_id(trace_id: str) -> tuple[str, str]:
    m = ID_RE.match(str(trace_id or ""))
    if not m:
        raise InvalidId(f"malformed TRACE id: {trace_id!r}")
    type_, slug = m.group(1), m.group(2)
    if type_ not in OBJECT_TYPES:
        raise InvalidId(f"unknown object type in id: {trace_id!r}")
    return type_, slug


def is_valid_id(trace_id: str) -> bool:
    try:
        parse_id(trace_id)
        return True
    except InvalidId:
        return False


def type_of(trace_id: str) -> str:
    return parse_id(trace_id)[0]


# --- convenience constructors mirroring the examples in PLAN §3.1 ----------

def result_id(prms_result_id: str | int) -> str:
    return make_id("result", f"prms-{prms_result_id}")


def kp_id(handle: str) -> str:
    return make_id("kp", "hdl-" + slugify(handle.replace("https://hdl.handle.net/", "")))


def program_id(code: str) -> str:
    return make_id("program", code)


def aow_id(program_code: str, aow_code: str) -> str:
    return make_id("aow", f"{program_code}-{aow_code}")


def country_id(iso2: str) -> str:
    return make_id("country", iso2.lower())


def institution_id(clarisa_id: str | int) -> str:
    return make_id("institution", f"clarisa-{clarisa_id}")


def concept_id(term_id: str) -> str:
    return make_id("concept", term_id)


def project_id(program: str, center: str, title: str) -> str:
    return make_id("project", f"porb-{sha1_12(program, center, title)}")


def melia_id(program: str, center: str, title: str) -> str:
    return make_id("melia_study", f"porb-{sha1_12(program, center, title)}")


# --- alt id resolution -----------------------------------------------------

def normalise_alt_id(scheme: str, value: str) -> tuple[str, str]:
    """Canonical form for alt-id lookups (case/prefix insensitive where sensible)."""
    scheme = (scheme or "").strip().lower()
    v = str(value or "").strip()
    if scheme == "cgspace_handle":
        v = v.replace("https://hdl.handle.net/", "").replace("http://hdl.handle.net/", "")
        v = v.replace("https://cgspace.cgiar.org/handle/", "").strip("/")
    elif scheme == "doi":
        v = v.lower().replace("https://doi.org/", "").replace("http://doi.org/", "")
    elif scheme == "iso2":
        v = v.upper()
    return scheme, v


def resolve_alt_id(scheme: str, value: str) -> str | None:
    """alt-id → TRACE object id (None when unknown)."""
    from app.db import query_one

    scheme, v = normalise_alt_id(scheme, value)
    row = query_one("SELECT object_id FROM alt_ids WHERE scheme=? AND value=?", (scheme, v))
    if row:
        return row["object_id"]
    row = query_one(
        "SELECT object_id FROM alt_ids WHERE scheme=? AND lower(value)=lower(?)", (scheme, v)
    )
    return row["object_id"] if row else None


def resolve_any(candidates: Iterable[tuple[str, str]]) -> str | None:
    for scheme, value in candidates:
        found = resolve_alt_id(scheme, value)
        if found:
            return found
    return None

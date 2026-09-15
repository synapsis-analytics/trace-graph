"""Lens loading, edge filtering and plain-English path explanation (PLAN §3.6)."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Iterable

import yaml

from app.config import get_settings
from app.ids import is_valid_id, type_of

TYPE_LABEL = {
    "program": "Program", "aow": "Area of Work", "hlo": "High-Level Output",
    "indicator": "Indicator", "outcome": "Outcome", "result": "Result",
    "kp": "Knowledge product", "innovation": "Innovation", "institution": "Institution",
    "country": "Country", "region": "Region", "project": "Project",
    "melia_study": "MELIA study", "concept": "Concept", "person": "Person", "document": "Document",
}

# forward phrase, inverse phrase
PREDICATE_PHRASE = {
    "PART_OF": ("is part of", "contains"),
    "CONTRIBUTES_TO": ("contributes to", "receives a contribution from"),
    "REPORTED_UNDER": ("is reported under", "is the reporting programme of"),
    "PRODUCED_BY": ("was produced by", "produced"),
    "WITH_PARTNER": ("was delivered with partner", "partnered on"),
    "LOCATED_IN": ("is located in", "is a location of"),
    "EVIDENCED_BY": ("is evidenced by", "is evidence for"),
    "SAME_AS": ("is the same thing as", "is the same thing as"),
    "DESCRIBES": ("describes", "is described by"),
    "FUNDED_BY": ("is funded by", "funds"),
    "STUDIED_BY": ("is studied by", "studies"),
    "SYNERGY_WITH": ("has a synergy with", "has a synergy with"),
    "TAGGED_WITH": ("is tagged with", "tags"),
    "BROADER": ("has the broader concept", "has the narrower concept"),
    "CANDIDATE_FOR": ("is a candidate for", "has the candidate term"),
    "AUTHORED_BY": ("was authored by", "authored"),
}


@lru_cache(maxsize=4)
def _load_cached(path: str, mtime: float) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    lenses = data.get("lenses") or {}
    for name, lens in lenses.items():
        lens["name"] = name
        steps: set[tuple[str, str, str]] = set()
        predicates: set[str] = set()
        types: set[str] = set()
        for path_def in lens.get("paths") or []:
            for i in range(0, len(path_def) - 2, 2):
                a, p, b = path_def[i], path_def[i + 1], path_def[i + 2]
                steps.add((a, p, b))
                predicates.add(p)
                types.update([a, b])
        lens["_steps"] = steps
        lens["predicates"] = sorted(predicates)
        lens["types"] = sorted(types)
        excl: set[tuple[str, str, str]] = set()
        for e in lens.get("excludes") or []:
            if len(e) == 3:
                excl.add((e[0], e[1], e[2]))
        lens["_excludes"] = excl
    data["lenses"] = lenses
    return data


def load_lenses() -> dict[str, dict]:
    p = get_settings().lenses_path
    try:
        return _load_cached(str(p), p.stat().st_mtime)["lenses"]
    except FileNotFoundError:  # pragma: no cover - defensive
        return {}


def lens_names() -> list[str]:
    return sorted(load_lenses().keys())


def get_lens(name: str | None) -> dict | None:
    if not name:
        return None
    return load_lenses().get(name)


def lens_definitions() -> list[dict]:
    """Public JSON for GET /api/lenses (internal caches stripped)."""
    out = []
    for name, lens in sorted(load_lenses().items()):
        out.append({
            "name": name,
            "label": lens.get("label", name.title()),
            "description": (lens.get("description") or "").strip(),
            "paths": lens.get("paths") or [],
            "predicates": lens.get("predicates", []),
            "types": lens.get("types", []),
            "excludes": lens.get("excludes") or [],
            "boundary_attrs": lens.get("boundary_attrs") or [],
            "notes": (lens.get("notes") or "").strip(),
        })
    return out


def allowed(predicate: str, from_type: str, to_type: str, lens: str | dict | None) -> bool:
    """Is a (from_type)-[predicate]->(to_type) step walkable under this lens?"""
    spec = get_lens(lens) if isinstance(lens, str) or lens is None else lens
    if spec is None:
        return True
    if (from_type, predicate, to_type) in spec["_excludes"] or ("any", predicate, to_type) in spec["_excludes"]:
        return False
    steps = spec["_steps"]
    return (from_type, predicate, to_type) in steps or ("*", predicate, "*") in steps


def allowed_edge(subject: str, predicate: str, obj: str, lens: str | dict | None) -> bool:
    if lens is None:
        return True
    if not (is_valid_id(subject) and is_valid_id(obj)):
        return False
    return allowed(predicate, type_of(subject), type_of(obj), lens)


def phrase(predicate: str, inverse: bool = False) -> str:
    fwd, inv = PREDICATE_PHRASE.get(predicate, (predicate.lower().replace("_", " "),
                                                "is " + predicate.lower().replace("_", " ") + " of"))
    return inv if inverse else fwd


def _describe(node: dict) -> str:
    label = node.get("label") or node.get("id")
    t = TYPE_LABEL.get(node.get("type", ""), node.get("type", "Object"))
    return f'{t} "{label}"'


def explain_path(path: Iterable[dict]) -> str:
    """Plain English for a path.

    ``path`` is the step list produced by :func:`app.graph.shortest_path`:
    ``[{"from": node, "predicate": str, "direction": "out"|"in", "to": node}, …]``.
    """
    steps = list(path)
    if not steps:
        return ""
    parts: list[str] = []
    for i, step in enumerate(steps):
        verb = phrase(step["predicate"], inverse=step.get("direction") == "in")
        head = _describe(step["from"]) if i == 0 else "which"
        parts.append(f"{head} {verb} {_describe(step['to'])}")
    sentence = ", ".join(parts)
    return sentence[0].upper() + sentence[1:] + "."

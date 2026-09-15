"""TRACE intake channel: **taxonomy tagging & reconciliation** (MELIAF taxonomy service).

Reads the claim batches produced by the other channels, sends every taggable object's text to
the MELIAF taxonomy service ``POST /api/resolve`` (layers 2 = CGIAR Lexicon and 3 = climate
adaptation), and emits:

* ``concept`` objects for every referenced term **and its broader chain**,
* ``BROADER`` links concept → concept,
* ``TAGGED_WITH`` links object → concept with ``{matched_text, via, layer, start, end, hits}``,
* ``candidate_concept`` claims for the frequent free terms (CGSpace ``dcterms.subject`` values and
  PRMS result-title phrases) that have **no** Layer-2/3 match — Jules' reconciliation queue.

    python -m ingest.taxonomy --base http://localhost:8420 --claims 'data/claims/seed-*.jsonl' \
        --out data/claims/seed-taxonomy.jsonl --vendor data/seed/taxonomy_v0.2.0.json

If the service is unreachable the channel falls back to resolving **locally** against the
vendored export with the same case-insensitive whole-word label/alt-label matching, sets
``attrs.via="local_fallback"`` and says so in the summary (and in SEED-REPORT.md).
"""
from __future__ import annotations

import argparse
import glob as _glob
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from ingest import common as C

CHANNEL = "taxonomy"
SYSTEM = "taxonomy"

DEFAULT_BASE = "http://localhost:8420"
TAGGABLE_TYPES = ("result", "kp", "hlo", "outcome", "indicator", "melia_study", "project")
LAYERS = (2, 3)
BAND_BY_VIA = {"pref_label": "high", "alt_label": "medium", "stem": "medium"}

STOPWORDS = set("""a an and are as at be by for from has have in into is it its of on or that the
to with without their there this these those we our using use used new more than over under
between across within during after before towards toward through study studies report reports
data results result project projects program programme approach approaches based level levels
key high low first second third can will may also such other others among both each per via
""".split())


# --------------------------------------------------------------------------------------
# Vendored export
# --------------------------------------------------------------------------------------
SLIM_FIELDS = ("id", "uri", "pref_label", "alt_labels", "definition", "layer", "source",
               "status", "parents", "kind", "path", "replaced_by", "notes")


def fetch_export(base: str, vendor: str, timeout: float = 60.0) -> dict[str, Any]:
    """Download + vendor a slimmed copy of the current taxonomy export (offline/tests)."""
    import httpx
    with httpx.Client(timeout=timeout) as client:
        r = client.get(f"{base}/api/export/current.json")
        r.raise_for_status()
        data = r.json()
        if str(data.get("version") or "").lower() in ("", "current"):
            # /api/export/current.json labels itself "current"; resolve the real version
            try:
                data["version"] = client.get(f"{base}/health").json().get("version_current")
            except Exception:  # noqa: BLE001 - keep whatever the export said
                pass
    slim = {
        "version": data.get("version"),
        # NB: the service stamps `created_at` with the moment the export was generated, which
        # would make this vendored file churn on every download — we use the (frozen) ingest
        # clock instead so the committed copy is byte-stable.
        "exported_at": C.now_iso(),
        "author": data.get("author"),
        "notes": ("Slimmed vendored copy of the MELIAF taxonomy export (fields: "
                  + ", ".join(SLIM_FIELDS) + "). Definitions trimmed to 600 chars. "
                  "The full export stays available from the taxonomy service."),
        "source": f"{base}/api/export/current.json",
        "n_terms": len(data.get("terms", [])),
        # sorted by id so the vendored copy is byte-stable across downloads
        "terms": sorted(
            ({**{k: t.get(k) for k in SLIM_FIELDS},
              "definition": C.trim(t.get("definition"), 600)}
             for t in data.get("terms", [])),
            key=lambda t: str(t.get("id")),
        ),
    }
    C.write_extract(vendor, slim)
    return slim


def load_vendor(vendor: str) -> dict[str, Any]:
    p = Path(vendor)
    if not p.exists():
        return {"version": None, "terms": []}
    return json.loads(p.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------------------
# Local (offline) resolver — same matching rule as the service's label/alt-label pass
# --------------------------------------------------------------------------------------
class LocalResolver:
    def __init__(self, terms: Iterable[dict[str, Any]], layers: Iterable[int] = LAYERS):
        self.terms = {t["id"]: t for t in terms}
        self.layers = set(layers)
        self.index: dict[str, tuple[str, str]] = {}
        for t in self.terms.values():
            if t.get("layer") not in self.layers:
                continue
            for label in [t.get("pref_label")] + list(t.get("alt_labels") or []):
                if label and len(str(label)) >= 4:
                    self.index.setdefault(str(label).lower(), (t["id"], "pref_label"
                                          if label == t.get("pref_label") else "alt_label"))

    def resolve(self, text: str) -> list[dict[str, Any]]:
        low = (text or "").lower()
        out = []
        for label, (term_id, via) in self.index.items():
            for m in re.finditer(r"(?<![a-z0-9])" + re.escape(label) + r"(?![a-z0-9])", low):
                t = self.terms[term_id]
                out.append({"term_id": term_id, "pref_label": t.get("pref_label"),
                            "matched_text": text[m.start():m.end()], "start": m.start(),
                            "end": m.end(), "layer": t.get("layer"), "via": via,
                            "uri": t.get("uri"), "status": t.get("status"),
                            "definition": t.get("definition"), "source": t.get("source")})
                break
        return out


# --------------------------------------------------------------------------------------
def load_objects(patterns: list[str], exclude: str) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Collect objects (merged with later assert_attr claims) from the batches."""
    files: list[str] = []
    for pat in patterns:
        files.extend(sorted(_glob.glob(pat)))
    files = [f for f in dict.fromkeys(files) if Path(f).resolve() != Path(exclude).resolve()]
    objects: dict[str, dict[str, Any]] = {}
    attrs_by_id: dict[str, dict[str, Any]] = defaultdict(dict)
    for f in files:
        for claim in C.read_batch(f):
            if claim["kind"] == "assert_object":
                objects.setdefault(claim["payload"]["id"], claim["payload"])
            elif claim["kind"] == "assert_attr":
                attrs_by_id[claim["subject"]].update(claim["payload"].get("attrs", {}))
    for oid, extra in attrs_by_id.items():
        if oid in objects:
            merged = dict(objects[oid].get("attrs") or {})
            merged.update(extra)
            objects[oid]["attrs"] = merged
        else:
            objects[oid] = {"id": oid, "type": _type_of(oid), "label": extra.get("title") or oid,
                            "description": extra.get("abstract"), "attrs": extra}
    return objects, files


def _type_of(oid: str) -> str:
    parts = oid.split(":")
    return parts[1] if len(parts) > 2 else "unknown"


def object_text(obj: dict[str, Any]) -> str:
    attrs = obj.get("attrs") or {}
    bits = [obj.get("label") or "", obj.get("description") or attrs.get("abstract") or ""]
    if obj.get("type") == "kp" and attrs.get("subjects"):
        bits.append("; ".join(attrs["subjects"][:15]))
    if obj.get("type") == "indicator" and attrs.get("kpi_type"):
        bits.append(str(attrs["kpi_type"]))
    text = ". ".join(b for b in bits if b)
    return C.trim(text, 4000) or (obj.get("label") or "")


# --------------------------------------------------------------------------------------
def candidate_terms(objects: dict[str, dict[str, Any]], resolver: LocalResolver,
                    top: int = 40) -> list[dict[str, Any]]:
    """Frequent free terms with no Layer-2/3 match → the reconciliation queue."""
    counts: Counter[str] = Counter()
    contexts: dict[str, list[str]] = defaultdict(list)
    layer1 = {str(t.get("pref_label", "")).lower() for t in resolver.terms.values()
              if t.get("layer") == 1}

    def add(term: str, ctx: str) -> None:
        term = re.sub(r"\s+", " ", term).strip(" .,:;—-")
        if len(term) < 4 or len(term) > 60:
            return
        if term.lower() in STOPWORDS or term.isdigit():
            return
        counts[term.lower()] += 1
        if len(contexts[term.lower()]) < 5:
            contexts[term.lower()].append(ctx)

    for obj in objects.values():
        attrs = obj.get("attrs") or {}
        if obj.get("type") == "kp":
            for subject in attrs.get("subjects", []) or []:
                add(subject, obj.get("label") or obj["id"])
        elif obj.get("type") == "result":
            title = obj.get("label") or ""
            words = [w for w in re.findall(r"[A-Za-z][A-Za-z\-']+", title)]
            for n in (2, 3):
                for i in range(len(words) - n + 1):
                    gram = words[i:i + n]
                    if gram[0].lower() in STOPWORDS or gram[-1].lower() in STOPWORDS:
                        continue
                    add(" ".join(gram), title)

    out = []
    for term, n in counts.most_common():
        if resolver.resolve(term):
            continue  # already covered by Layer 2/3
        out.append({"term": term, "hits": n, "contexts": contexts[term],
                    "in_layer1": term in layer1})
        if len(out) >= top:
            break
    return out


# --------------------------------------------------------------------------------------
def run(base: str, claims_patterns: list[str], out: str, vendor: str,
        refresh_vendor: bool = True, timeout: float = 15.0) -> dict[str, Any]:
    reachable = False
    version = None
    export: dict[str, Any] = {}
    if refresh_vendor:
        try:
            export = fetch_export(base, vendor)
            reachable = True
        except Exception as exc:  # noqa: BLE001
            print(f"[taxonomy] export download failed ({exc.__class__.__name__}: {exc}); "
                  f"using vendored copy")
    if not export:
        export = load_vendor(vendor)
    terms = {t["id"]: t for t in export.get("terms", [])}
    version = export.get("version")
    resolver = LocalResolver(terms.values())

    objects, files = load_objects(claims_patterns, out)
    taggable = [o for o in objects.values() if o.get("type") in TAGGABLE_TYPES]
    taggable.sort(key=lambda o: o["id"])

    # --- resolve ----------------------------------------------------------------------
    matches_by_object: dict[str, list[dict[str, Any]]] = {}
    service_ok = False
    client = None
    if reachable or refresh_vendor:
        try:
            import httpx
            client = httpx.Client(base_url=base, timeout=timeout)
            probe = client.post("/api/resolve", json={"text": "climate adaptation",
                                                      "layers": list(LAYERS)})
            probe.raise_for_status()
            version = probe.json().get("version") or version
            service_ok = True
        except Exception as exc:  # noqa: BLE001
            print(f"[taxonomy] resolve service unreachable ({exc}); local fallback")
            if client is not None:
                client.close()
            client = None

    try:
        for obj in taggable:
            text = object_text(obj)
            if not text:
                continue
            if service_ok and client is not None:
                try:
                    r = client.post("/api/resolve", json={"text": text, "layers": list(LAYERS)})
                    r.raise_for_status()
                    body = r.json()
                    version = body.get("version") or version
                    matches_by_object[obj["id"]] = body.get("matches", [])
                    continue
                except Exception as exc:  # noqa: BLE001
                    print(f"[taxonomy] resolve failed for {obj['id']}: {exc}; local fallback")
                    service_ok = False
            matches_by_object[obj["id"]] = [
                {**m, "via": "local_fallback:" + m["via"]} for m in resolver.resolve(text)]
    finally:
        if client is not None:
            client.close()

    # --- build claims -----------------------------------------------------------------
    claims: list[dict[str, Any]] = []
    seen_objects: set[str] = set()
    snapshot = f"taxonomy_{version or 'vendored'}"

    def concept_obj(term_id: str, ref: str) -> str | None:
        t = terms.get(term_id)
        cid = C.make_id("concept", term_id.lower())
        if cid in seen_objects:
            return cid
        seen_objects.add(cid)
        claims.append(C.object_claim(
            "concept", cid, (t or {}).get("pref_label") or term_id,
            channel=CHANNEL, system=SYSTEM, ref=ref, snapshot=snapshot,
            description=C.trim((t or {}).get("definition"), 1000),
            attrs={"pref_label": (t or {}).get("pref_label"),
                   "definition": C.trim((t or {}).get("definition"), 1000),
                   "layer": (t or {}).get("layer"), "status": (t or {}).get("status"),
                   "uri": (t or {}).get("uri"), "source": (t or {}).get("source"),
                   "alt_labels": (t or {}).get("alt_labels") or [],
                   "path": (t or {}).get("path"), "kind": (t or {}).get("kind")},
            alt_ids=[{"scheme": "taxonomy_term_id", "value": term_id}] +
                    ([{"scheme": "taxonomy_uri", "value": (t or {}).get("uri")}]
                     if (t or {}).get("uri") else []),
            taxonomy_version=version, band="high"))
        return cid

    def add_broader_chain(term_id: str) -> None:
        """Walk ``parents`` up to the root, creating concepts and BROADER links."""
        current, depth = term_id, 0
        while depth < 8:
            t = terms.get(current)
            if not t:
                return
            parents = [p for p in (t.get("parents") or []) if p and p in terms]
            if not parents:
                return
            parent = parents[0]
            concept_obj(parent, f"taxonomy term {parent}")
            claims.append(C.link_claim(
                C.make_id("concept", current.lower()), "BROADER",
                C.make_id("concept", parent.lower()),
                channel=CHANNEL, system=SYSTEM, ref=f"taxonomy parents of {current}",
                snapshot=snapshot, attrs={"via": "skos:broader"},
                taxonomy_version=version, band="high"))
            current, depth = parent, depth + 1

    pair_stats: Counter[str] = Counter()
    for obj in taggable:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for m in matches_by_object.get(obj["id"], []):
            if m.get("term_id"):
                grouped[m["term_id"]].append(m)
        for term_id, ms in grouped.items():
            best = ms[0]
            cid = concept_obj(term_id, f"resolve({obj['id']})")
            add_broader_chain(term_id)
            via = str(best.get("via") or "")
            band = BAND_BY_VIA.get(via.split(":")[-1], "medium")
            pair_stats[via.split(":")[-1]] += 1
            claims.append(C.link_claim(
                obj["id"], "TAGGED_WITH", cid, channel=CHANNEL, system=SYSTEM,
                ref=f"POST /api/resolve ({obj['id']})", snapshot=snapshot,
                attrs={"matched_text": best.get("matched_text"), "via": via,
                       "layer": best.get("layer"), "start": best.get("start"),
                       "end": best.get("end"), "hits": len(ms),
                       "confidence": 0.95 if band == "high" else 0.7,
                       "object_type": obj.get("type")},
                taxonomy_version=version, band=band,
                evidence=[{"kind": "text", "value": C.trim(best.get("matched_text"), 120) or ""}]
                if best.get("matched_text") else None))

    # --- candidate concepts ------------------------------------------------------------
    candidates = candidate_terms(objects, resolver)
    for cand in candidates:
        claims.append(C.candidate_concept_claim(
            cand["term"], channel=CHANNEL, system=SYSTEM,
            ref="frequent unmatched term (CGSpace dcterms.subject / PRMS result titles)",
            snapshot=snapshot, count=cand["hits"], contexts=cand["contexts"],
            taxonomy_version=version, suggested_layer=2))

    claims = C.dedupe_links(C.dedupe_objects(claims))
    n = C.write_batch(out, claims)
    summary = C.summarise(claims)
    summary.update(channel=CHANNEL, out=out, claims=n, taxonomy_version=version,
                   service_reachable=service_ok, vendored=vendor,
                   objects_resolved=len(matches_by_object), tagged_objects=sum(
                       1 for v in matches_by_object.values() if v),
                   via_breakdown=dict(pair_stats), candidates=len(candidates),
                   batches_read=files)
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="TRACE intake channel: taxonomy tagging")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--claims", nargs="+", default=["data/claims/seed-*.jsonl"])
    ap.add_argument("--out", default="data/claims/seed-taxonomy.jsonl")
    ap.add_argument("--vendor", default="data/seed/taxonomy_v0.2.0.json")
    ap.add_argument("--no-refresh-vendor", action="store_true")
    a = ap.parse_args(argv)
    s = run(a.base, a.claims, a.out, a.vendor, refresh_vendor=not a.no_refresh_vendor)
    print(f"[taxonomy] {s['claims']} claims -> {s['out']} "
          f"(service={'live' if s['service_reachable'] else 'local fallback'}, "
          f"version={s['taxonomy_version']})")
    print(f"           objects: {s['objects']}")
    print(f"           links:   {s['links']}")
    print(f"           tagged {s['tagged_objects']}/{s['objects_resolved']} objects; "
          f"{s['candidates']} candidate concepts; via {s['via_breakdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

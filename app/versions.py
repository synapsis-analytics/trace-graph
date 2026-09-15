"""Versioned snapshots of the accepted graph (PLAN §7.4): publish + export json/csv/graphml."""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.db import connect
from app.graph import export_graph
from app.registry import now_iso

VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def list_versions() -> list[dict[str, Any]]:
    with connect(readonly=True) as conn:
        return [
            {"version": r["version"], "created_at": r["created_at"], "notes": r["notes"],
             "path": r["path"], "counts": json.loads(r["counts_json"] or "{}")}
            for r in conn.execute("SELECT * FROM versions ORDER BY created_at DESC")
        ]


def latest_version() -> str | None:
    vs = list_versions()
    return vs[0]["version"] if vs else None


def next_version(bump: str = "minor") -> str:
    cur = latest_version() or "v0.0.0"
    m = VERSION_RE.match(cur)
    major, minor, patch = (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else (0, 0, 0)
    if bump == "major":
        major, minor, patch = major + 1, 0, 0
    elif bump == "patch":
        patch += 1
    else:
        minor, patch = minor + 1, 0
    return f"v{major}.{minor}.{patch}"


def publish(bump: str = "minor", notes: str = "") -> dict[str, Any]:
    version = next_version(bump)
    settings = get_settings()
    settings.versions_dir.mkdir(parents=True, exist_ok=True)
    payload = export_graph(version)
    payload["created_at"] = now_iso()
    payload["notes"] = notes
    payload["env"] = settings.env
    path = settings.versions_dir / f"{version}.json"
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    with connect() as conn:
        claims = conn.execute("SELECT COUNT(*) c FROM claims WHERE status='accepted'").fetchone()["c"]
        counts = {**payload["counts"], "accepted_claims": claims}
        conn.execute(
            "INSERT INTO versions(version, created_at, notes, path, counts_json) VALUES(?,?,?,?,?) "
            "ON CONFLICT(version) DO UPDATE SET created_at=excluded.created_at, notes=excluded.notes, "
            "path=excluded.path, counts_json=excluded.counts_json",
            (version, payload["created_at"], notes, str(path), json.dumps(counts)),
        )
    return {"version": version, "path": str(path), "counts": counts, "notes": notes,
            "created_at": payload["created_at"]}


def _load(version: str) -> dict[str, Any]:
    settings = get_settings()
    v = version if version.startswith("v") else f"v{version}"
    path = settings.versions_dir / f"{v}.json"
    if not path.exists():
        raise FileNotFoundError(f"version {v} not published")
    return json.loads(path.read_text(encoding="utf-8"))


def export(version: str, fmt: str = "json") -> tuple[str, str]:
    """Returns (content, media_type)."""
    data = _load(version)
    if fmt == "json":
        return json.dumps(data, indent=1, ensure_ascii=False), "application/json"
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["kind", "id", "type_or_predicate", "label_or_source", "target", "attrs"])
        for n in data["nodes"]:
            w.writerow(["node", n["id"], n["type"], n["label"], "", json.dumps(n.get("attrs", {}))])
        for e in data["edges"]:
            w.writerow(["edge", e["id"], e["predicate"], e["source"], e["target"],
                        json.dumps(e.get("attrs", {}))])
        return buf.getvalue(), "text/csv"
    if fmt == "graphml":
        return _graphml(data), "application/xml"
    raise ValueError(f"unsupported format {fmt}")


def _graphml(data: dict) -> str:
    import networkx as nx

    g = nx.DiGraph()
    for n in data["nodes"]:
        g.add_node(n["id"], label=str(n.get("label") or ""), type=str(n.get("type") or ""),
                   band=str(n.get("band") or ""), size=float(n.get("size") or 1.0))
    for e in data["edges"]:
        if e["source"] in g and e["target"] in g:
            g.add_edge(e["source"], e["target"], predicate=str(e.get("predicate") or ""),
                       id=str(e.get("id") or ""))
    buf = io.BytesIO()
    nx.write_graphml(g, buf)
    return buf.getvalue().decode("utf-8")


def export_to_file(version: str, fmt: str, out_dir: Path | None = None) -> Path:
    content, _ = export(version, fmt)
    out_dir = out_dir or get_settings().versions_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{version}.{fmt}"
    path.write_text(content, encoding="utf-8")
    return path

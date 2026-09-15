"""Versions: publish, list, export json/csv/graphml, CLI surface."""
from __future__ import annotations

import json

from app import versions as ver
from app.cli import main as cli_main
from tests.conftest import IDS


def test_publish_and_list(seeded):
    out = ver.publish(bump="minor", notes="first seed")
    assert out["version"] == "v0.1.0"
    assert out["counts"]["nodes"] == 23 and out["counts"]["accepted_claims"] >= 50
    listed = ver.list_versions()
    assert listed[0]["version"] == "v0.1.0" and listed[0]["notes"] == "first seed"
    assert ver.latest_version() == "v0.1.0"


def test_bumping(seeded):
    ver.publish(bump="minor")
    assert ver.next_version("patch") == "v0.1.1"
    assert ver.next_version("minor") == "v0.2.0"
    assert ver.next_version("major") == "v1.0.0"


def test_export_formats(seeded):
    ver.publish(bump="minor", notes="export test")
    as_json, media = ver.export("v0.1.0", "json")
    assert media == "application/json"
    data = json.loads(as_json)
    assert any(n["id"] == IDS["result"] for n in data["nodes"])
    as_csv, media_csv = ver.export("v0.1.0", "csv")
    assert media_csv == "text/csv" and as_csv.splitlines()[0].startswith("kind,id")
    as_graphml, media_x = ver.export("v0.1.0", "graphml")
    assert media_x == "application/xml" and "<graphml" in as_graphml and IDS["kp"] in as_graphml


def test_export_endpoint(client, key_headers):
    client.post("/api/versions/publish", json={"bump": "minor", "notes": "api"}, headers=key_headers)
    assert client.get("/api/versions").json()["latest"] == "v0.1.0"
    assert client.get("/api/export/v0.1.0.json").status_code == 200
    assert client.get("/api/export/v0.1.0.csv").headers["content-type"].startswith("text/csv")
    assert client.get("/api/export/v9.9.9.json").status_code == 404
    assert client.get("/api/export/v0.1.0.txt").status_code == 400


def test_publish_requires_key(client):
    assert client.post("/api/versions/publish", json={"bump": "minor"}).status_code == 401


def test_cli_rebuild_load_publish_export(seeded, tmp_path, capsys):
    assert cli_main(["rebuild"]) == 0
    assert cli_main(["qa-rerun"]) == 0
    assert cli_main(["publish", "--bump", "patch", "--notes", "cli"]) == 0
    out_file = tmp_path / "snapshot.graphml"
    assert cli_main(["export", "v0.0.1", "graphml", "--out", str(out_file)]) == 0
    assert out_file.exists() and "<graphml" in out_file.read_text()
    assert cli_main(["stats"]) == 0
    printed = capsys.readouterr().out
    assert '"objects"' in printed


def test_cli_load_missing_file(tmp_path):
    assert cli_main(["load", str(tmp_path / "nope-*.jsonl")]) == 2

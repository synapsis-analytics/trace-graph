"""Shared pytest fixtures: isolated temp DB, no network, fixture claim batch loaded."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
FIXTURE_BATCH = REPO / "tests" / "fixtures" / "claims" / "fixture-seed-20260915.jsonl"


@pytest.fixture(autouse=True, scope="session")
def _env(tmp_path_factory):
    """Point every test at a throwaway DB and disable outbound calls."""
    db = tmp_path_factory.mktemp("trace-db") / "test.db"
    os.environ.update({
        "TRACE_ENV": "test",
        "TRACE_DB_PATH": str(db),
        "TRACE_DATA_DIR": str(db.parent / "data"),   # versions/exports never touch the repo
        "TRACE_ACCESS_KEY": "test-key",
        "TAXONOMY_BASE_URL": "",          # no network: client degrades to the vendored copy
        "OPENAI_API_KEY": "",             # /api/ask must answer 503
        "TRACE_PUBLIC_URL": "http://testserver",
    })
    from app.config import reset_settings
    from app.db import init_db, reset_state
    from app.taxonomy_client import reset_client

    reset_settings()
    reset_state()
    reset_client()
    init_db()
    yield


@pytest.fixture(scope="function")
def clean_db():
    """Empty registry + graph before a test that wants full control."""
    from app.db import connect

    with connect() as conn:
        for table in ("links", "alt_ids", "objects_fts", "objects", "claims", "versions", "ingest_runs"):
            conn.execute(f"DELETE FROM {table}")
    yield


@pytest.fixture(scope="function")
def seeded(clean_db):
    """The fixture claim batch loaded through the registry."""
    from app.registry import load_batch

    summary = load_batch(FIXTURE_BATCH)
    yield summary


@pytest.fixture()
def client(seeded):
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def key_headers():
    return {"X-Access-Key": "test-key"}


IDS = {
    "program": "trace:program:sp01",
    "aow": "trace:aow:sp01-aow01",
    "hlo": "trace:hlo:sp01-hlo2-aow1-io1",
    "indicator": "trace:indicator:sp01-hlo2-aow1-io1-kpi1",
    "outcome": "trace:outcome:sp01-i-oc-3-5",
    "result": "trace:result:prms-24338",
    "result2": "trace:result:prms-24401",
    "kp": "trace:kp:hdl-10568-175922",
    "institution": "trace:institution:clarisa-3",
    "partner": "trace:institution:clarisa-1234",
    "country": "trace:country:ke",
    "project": "trace:project:porb-a1b2c3d4e5f6",
    "concept": "trace:concept:l2-0074",
}

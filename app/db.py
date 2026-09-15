"""SQLite access layer: per-request connections, WAL, schema migrations on start."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.config import get_settings

SCHEMA = [
    # objects -------------------------------------------------------------
    """CREATE TABLE IF NOT EXISTS objects (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        label TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        attrs_json TEXT NOT NULL DEFAULT '{}',
        alt_ids_json TEXT NOT NULL DEFAULT '[]',
        source_json TEXT NOT NULL DEFAULT '{}',
        qa_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_objects_type ON objects(type)",
    """CREATE TABLE IF NOT EXISTS alt_ids (
        scheme TEXT NOT NULL,
        value TEXT NOT NULL,
        object_id TEXT NOT NULL,
        PRIMARY KEY (scheme, value)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_alt_ids_object ON alt_ids(object_id)",
    # links ---------------------------------------------------------------
    """CREATE TABLE IF NOT EXISTS links (
        id TEXT PRIMARY KEY,
        subject TEXT NOT NULL,
        predicate TEXT NOT NULL,
        object TEXT NOT NULL,
        attrs_json TEXT NOT NULL DEFAULT '{}',
        claim_id TEXT,
        qa_json TEXT NOT NULL DEFAULT '{}'
    )""",
    "CREATE INDEX IF NOT EXISTS idx_links_subject ON links(subject, predicate)",
    "CREATE INDEX IF NOT EXISTS idx_links_object ON links(object, predicate)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_links_triple ON links(subject, predicate, object)",
    # claims --------------------------------------------------------------
    """CREATE TABLE IF NOT EXISTS claims (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        subject TEXT,
        predicate TEXT,
        object TEXT,
        payload_json TEXT NOT NULL DEFAULT '{}',
        attested_by TEXT,
        provenance TEXT,
        signature TEXT,
        evidence_json TEXT NOT NULL DEFAULT '[]',
        taxonomy_version TEXT,
        source_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        supersedes TEXT,
        qa_json TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'review',
        decided_by TEXT,
        decided_at TEXT,
        seq INTEGER
    )""",
    "CREATE INDEX IF NOT EXISTS idx_claims_subject ON claims(subject)",
    "CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(status)",
    "CREATE INDEX IF NOT EXISTS idx_claims_kind ON claims(kind)",
    "CREATE INDEX IF NOT EXISTS idx_claims_supersedes ON claims(supersedes)",
    # fts -----------------------------------------------------------------
    "CREATE VIRTUAL TABLE IF NOT EXISTS objects_fts USING fts5(id UNINDEXED, label, description)",
    # versions & agents ---------------------------------------------------
    """CREATE TABLE IF NOT EXISTS versions (
        version TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        notes TEXT,
        path TEXT,
        counts_json TEXT NOT NULL DEFAULT '{}'
    )""",
    """CREATE TABLE IF NOT EXISTS agents (
        id TEXT PRIMARY KEY,
        name TEXT,
        secret_hash TEXT,
        kind TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ingest_runs (
        channel TEXT NOT NULL,
        ran_at TEXT NOT NULL,
        counts_json TEXT NOT NULL DEFAULT '{}'
    )""",
    "CREATE INDEX IF NOT EXISTS idx_ingest_runs ON ingest_runs(channel, ran_at)",
]

_init_lock = threading.Lock()
_initialised: set[str] = set()


def db_path() -> Path:
    return get_settings().db_path


def _configure(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA synchronous=NORMAL")


def init_db(path: Path | None = None) -> None:
    """Create/upgrade the schema. Idempotent, safe to call repeatedly."""
    p = Path(path) if path else db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with _init_lock:
        conn = sqlite3.connect(str(p))
        try:
            _configure(conn)
            for stmt in SCHEMA:
                conn.execute(stmt)
            conn.commit()
        finally:
            conn.close()
        _initialised.add(str(p))


@contextmanager
def connect(readonly: bool = False) -> Iterator[sqlite3.Connection]:
    """A fresh connection per call (never shared across threads)."""
    p = db_path()
    if str(p) not in _initialised:
        init_db(p)
    conn = sqlite3.connect(str(p), timeout=15.0)
    try:
        _configure(conn)
        yield conn
        if not readonly:
            conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:  # pragma: no cover - defensive
            pass
        raise
    finally:
        conn.close()


def reset_state() -> None:
    """Forget which files were initialised (tests switch DB paths)."""
    _initialised.clear()


def query(sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
    with connect(readonly=True) as conn:
        return list(conn.execute(sql, params))


def query_one(sql: str, params: tuple | list = ()):
    rows = query(sql, params)
    return rows[0] if rows else None

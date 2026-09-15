"""Configuration for the TRACE Graph backend (PLAN §5 env contract)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent

# .env is loaded once, non-overriding: real env vars (and pytest monkeypatch) win.
load_dotenv(REPO_ROOT / ".env", override=False)


def _abs(p: str) -> Path:
    path = Path(p).expanduser()
    return path if path.is_absolute() else (REPO_ROOT / path)


@dataclass
class Settings:
    env: str = field(default_factory=lambda: os.getenv("TRACE_ENV", "dev"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8413")))
    db_path: Path = field(default_factory=lambda: _abs(os.getenv("TRACE_DB_PATH", "data/trace.db")))
    access_key: str = field(default_factory=lambda: os.getenv("TRACE_ACCESS_KEY", "change-me"))
    taxonomy_base_url: str = field(
        default_factory=lambda: os.getenv("TAXONOMY_BASE_URL", "http://localhost:8420")
    )
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", "") or "")
    public_url: str = field(default_factory=lambda: os.getenv("TRACE_PUBLIC_URL", ""))
    ask_model: str = field(default_factory=lambda: os.getenv("TRACE_ASK_MODEL", "gpt-5.5"))
    data_dir: Path = field(default_factory=lambda: _abs(os.getenv("TRACE_DATA_DIR", "data")))
    repo_root: Path = REPO_ROOT

    @property
    def version(self) -> str:
        from app import __version__

        return __version__

    @property
    def versions_dir(self) -> Path:
        return self.data_dir / "versions"

    @property
    def claims_dir(self) -> Path:
        return self.data_dir / "claims"

    @property
    def frontend_dist(self) -> Path:
        return self.repo_root / "frontend" / "dist"

    @property
    def lenses_path(self) -> Path:
        return self.repo_root / "lenses.yaml"

    @property
    def qa_rules_path(self) -> Path:
        return self.repo_root / "qa" / "rules.yaml"


@lru_cache(maxsize=1)
def _cached() -> Settings:
    return Settings()


def get_settings() -> Settings:
    """Settings singleton. Call ``reset_settings()`` after changing the environment."""
    return _cached()


def reset_settings() -> Settings:
    _cached.cache_clear()
    return _cached()

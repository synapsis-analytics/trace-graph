"""Client for the MELIAF taxonomy service (PLAN D5). Degrades gracefully when it is down."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings

TIMEOUT = 5.0


class TaxonomyClient:
    def __init__(self, base_url: str | None = None, access_key: str | None = None):
        settings = get_settings()
        self.base_url = (base_url or settings.taxonomy_base_url or "").rstrip("/")
        self.access_key = access_key or ""
        self._seed_path = settings.repo_root / "data" / "seed" / "taxonomy_v0.2.0.json"

    # -- low level ---------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        return {"X-Access-Key": self.access_key} if self.access_key else {}

    def _get(self, path: str, params: dict | None = None) -> Any | None:
        if not self.base_url:
            return None
        try:
            r = httpx.get(self.base_url + path, params=params, timeout=TIMEOUT, headers=self._headers())
            if r.status_code >= 400:
                return None
            return r.json()
        except Exception:
            return None

    def _post(self, path: str, body: dict) -> Any | None:
        if not self.base_url:
            return None
        try:
            r = httpx.post(self.base_url + path, json=body, timeout=TIMEOUT, headers=self._headers())
            if r.status_code >= 400:
                return None
            return r.json()
        except Exception:
            return None

    # -- api ---------------------------------------------------------------
    def health(self) -> dict[str, Any]:
        data = self._get("/health")
        return {
            "url": self.base_url,
            "reachable": bool(data),
            "version": next((( data or {}).get(k) for k in
                             ("version_current", "current_version", "version", "taxonomy_version")
                             if (data or {}).get(k)), None),
            "detail": data or {},
            "offline_copy": self._seed_path.exists(),
        }

    def resolve(self, text: str, layer: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"text": text}
        if layer:
            body["layer"] = layer
        data = self._post("/api/resolve", body)
        if data is None:
            return {"matches": self._offline_resolve(text), "source": "offline-copy", "reachable": False}
        matches = data.get("matches") if isinstance(data, dict) else data
        return {"matches": matches or [], "source": "taxonomy-service", "reachable": True}

    def term(self, term_id: str) -> dict[str, Any] | None:
        data = self._get(f"/api/terms/{term_id}")
        if data:
            return data
        return self._offline_terms().get(term_id.upper())

    def export_current(self) -> dict[str, Any] | None:
        data = self._get("/api/export/current.json")
        if data:
            return data
        return self._offline_export()

    # -- offline fallback --------------------------------------------------
    def _offline_export(self) -> dict[str, Any] | None:
        if not self._seed_path.exists():
            return None
        try:
            return json.loads(self._seed_path.read_text(encoding="utf-8"))
        except Exception:  # pragma: no cover
            return None

    def _offline_terms(self) -> dict[str, dict]:
        exp = self._offline_export() or {}
        terms = exp.get("terms") or exp.get("concepts") or []
        out = {}
        for t in terms:
            tid = str(t.get("term_id") or t.get("id") or "").upper()
            if tid:
                out[tid] = t
        return out

    def _offline_resolve(self, text: str) -> list[dict]:
        """Very small deterministic matcher over the vendored export (exact pref/alt label hits)."""
        low = f" {(text or '').lower()} "
        matches = []
        for tid, t in self._offline_terms().items():
            labels = [t.get("pref_label") or ""] + list(t.get("alt_labels") or [])
            for lab in labels:
                if lab and f" {lab.lower()} " in low:
                    matches.append({
                        "term_id": tid, "pref_label": t.get("pref_label"), "matched_text": lab,
                        "layer": t.get("layer"), "via": "pref_label" if lab == t.get("pref_label") else "alt_label",
                        "uri": t.get("uri"), "status": t.get("status", "active"),
                    })
                    break
        return matches


@lru_cache(maxsize=1)
def get_client() -> TaxonomyClient:
    return TaxonomyClient()


def reset_client() -> None:
    get_client.cache_clear()

"""/api/stats, /api/coverage, /api/ingest, /api/tag, /api/ask, /api/versions, /api/export."""
from __future__ import annotations

import importlib
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app import objects as obj_svc
from app import versions as ver_svc
from app.api.deps import require_key
from app.config import get_settings
from app.graph import coverage as coverage_svc
from app.models import AskIn, IngestIn, PublishIn, TagIn
from app.tagging import tag_objects, tag_text

router = APIRouter(prefix="/api", tags=["ops"])

CHANNELS = ("prms", "cgspace", "porb", "toc", "taxonomy")


@router.get("/stats")
def stats():
    return obj_svc.stats()


@router.get("/coverage")
def coverage(layer: str | None = None, group: str | None = None,
             limit: int = Query(200, ge=1, le=1000)):
    return coverage_svc(layer=layer, group=group, limit=limit)


@router.post("/ingest/{channel}")
def ingest(channel: str, body: IngestIn | None = None, _key: str = Depends(require_key)):
    """Run an intake channel. Falls back to loading the channel's committed claim batches."""
    if channel not in CHANNELS:
        raise HTTPException(status_code=404, detail=f"unknown channel {channel}; use one of {CHANNELS}")
    limit = (body.limit if body else None)
    summary, module_error = None, None
    try:
        mod = importlib.import_module(f"ingest.{channel}")
    except ModuleNotFoundError as exc:
        mod, module_error = None, str(exc)
    if mod is not None:
        # the DATA agent owns ingest/; accept any of these entry points, keyword-only
        for fn_name in ("run_channel", "ingest", "run", "main"):
            fn = getattr(mod, fn_name, None)
            if not callable(fn):
                continue
            try:
                summary = fn(limit=limit)
                break
            except TypeError as exc:      # signature we do not know -> try the next one
                module_error = f"{fn_name}: {exc}"
            except Exception as exc:      # the channel itself failed -> report it
                raise HTTPException(status_code=500, detail=f"ingest.{channel}.{fn_name} failed: {exc}")
    if summary is None:
        from app.registry import load_batches

        batches = sorted(get_settings().claims_dir.glob(f"*{channel}*.jsonl"))
        if not batches:
            raise HTTPException(
                status_code=501,
                detail=(f"channel '{channel}' has no usable ingest entry point and no claim batch "
                        f"in data/claims/ ({module_error or 'no module'})"),
            )
        summary = {"channel": channel, "mode": "replay-batches", "batches": load_batches(list(batches))}
    obj_svc.record_ingest(channel, summary if isinstance(summary, dict) else {"summary": str(summary)})
    return {"channel": channel, "summary": summary}


@router.post("/tag")
def tag(body: TagIn, _key: str = Depends(require_key)):
    if body.object_ids:
        return tag_objects(body.object_ids)
    if body.text:
        return tag_text(body.text)
    raise HTTPException(status_code=400, detail="provide object_ids or text")


@router.post("/ask")
def ask_endpoint(body: AskIn):
    from app.ask import AskUnavailable, ask

    try:
        return ask(body.question)
    except AskUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:  # upstream failure
        raise HTTPException(status_code=502, detail=f"ask failed: {exc}")


@router.get("/versions")
def versions():
    return {"versions": ver_svc.list_versions(), "latest": ver_svc.latest_version()}


@router.post("/versions/publish")
def publish(body: PublishIn, _key: str = Depends(require_key)):
    return ver_svc.publish(bump=body.bump, notes=body.notes)


@router.get("/export/{filename}")
def export(filename: str):
    stem = Path(filename).stem
    fmt = Path(filename).suffix.lstrip(".").lower() or "json"
    if fmt not in ("json", "csv", "graphml"):
        raise HTTPException(status_code=400, detail="format must be json, csv or graphml")
    try:
        content, media = ver_svc.export(stem, fmt)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return Response(content=content, media_type=media,
                    headers={"Content-Disposition": f'inline; filename="{stem}.{fmt}"'})

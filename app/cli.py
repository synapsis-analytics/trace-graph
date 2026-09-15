"""Backend CLI: `python -m app.cli rebuild|load|qa-rerun|publish|export|stats|serve`."""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path


def _print(obj) -> None:
    print(json.dumps(obj, indent=1, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="TRACE Graph backend CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("rebuild", help="replay the claims log into fresh object/link tables")

    p_load = sub.add_parser("load", help="append claim batches (jsonl; globs allowed)")
    p_load.add_argument("paths", nargs="+")
    p_load.add_argument("--dry-run", action="store_true")

    sub.add_parser("qa-rerun", help="re-score every stored claim with the current qa/rules.yaml")

    p_pub = sub.add_parser("publish", help="freeze the accepted graph as a new version")
    p_pub.add_argument("--bump", choices=["major", "minor", "patch"], default="minor")
    p_pub.add_argument("--notes", default="")

    p_exp = sub.add_parser("export", help="export a published version")
    p_exp.add_argument("version")
    p_exp.add_argument("format", choices=["json", "csv", "graphml"], nargs="?", default="json")
    p_exp.add_argument("--out", default=None, help="write to this file instead of stdout")

    sub.add_parser("stats", help="registry/graph statistics")

    p_serve = sub.add_parser("serve", help="run uvicorn (dev convenience)")
    p_serve.add_argument("--port", type=int, default=None)

    args = parser.parse_args(argv)

    from app.config import get_settings
    from app.db import init_db

    init_db()

    if args.cmd == "rebuild":
        from app.registry import rebuild

        _print(rebuild())
    elif args.cmd == "load":
        from app.registry import load_batches

        files: list[str] = []
        for pattern in args.paths:
            hits = sorted(glob.glob(pattern))
            files.extend(hits or ([pattern] if Path(pattern).exists() else []))
        if not files:
            print("no matching claim batches", file=sys.stderr)
            return 2
        _print(load_batches(files, dry_run=args.dry_run))
    elif args.cmd == "qa-rerun":
        from app.qa import rerun_all
        from app.registry import rebuild

        out = rerun_all()
        out.update(rebuild())
        _print(out)
    elif args.cmd == "publish":
        from app.versions import publish

        _print(publish(bump=args.bump, notes=args.notes))
    elif args.cmd == "export":
        from app.versions import export

        content, _media = export(args.version, args.format)
        if args.out:
            Path(args.out).write_text(content, encoding="utf-8")
            _print({"written": args.out, "bytes": len(content)})
        else:
            print(content)
    elif args.cmd == "stats":
        from app.objects import stats

        _print(stats())
    elif args.cmd == "serve":  # pragma: no cover - interactive
        import uvicorn

        uvicorn.run("app.main:app", host="127.0.0.1", port=args.port or get_settings().port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""``python -m ingest.cli all`` — run every TRACE intake channel in order.

Order matters: **porb → prms → cgspace → toc → taxonomy**.

* ``porb`` first, because ``prms`` needs the PORB HLO sheet for the documented
  result → HLO heuristic;
* ``prms`` before ``cgspace``, because the CGSpace channel bridges on the PRMS handles;
* ``toc`` after both (it reads the PORB extract and the CGSpace registry);
* ``taxonomy`` last, because it tags the objects asserted by all of the above.

Re-running is idempotent: TRACE ids derive from source primary keys and claim ids from claim
content, so an unchanged source produces byte-identical batches (see ``ingest/common.py``).
"""
from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any

DEFAULT_ANCHOR = "2026-09-15T20:00:00Z"

CHANNEL_ORDER = ("porb", "prms", "cgspace", "toc", "taxonomy")


def _fmt(d: dict[str, Any] | None, width: int = 58) -> str:
    if not d:
        return "-"
    parts = [f"{k}={v}" for k, v in sorted(d.items(), key=lambda kv: -kv[1])]
    line = " ".join(parts)
    return line if len(line) <= width else line[: width - 1] + "…"


def run_all(args: argparse.Namespace) -> int:
    if not args.live_time and not os.environ.get("TRACE_INGEST_NOW"):
        os.environ["TRACE_INGEST_NOW"] = args.anchor
    # import AFTER the env var is set (ingest.common freezes the clock at import time)
    from ingest import cgspace, common, porb, prms, taxonomy, toc  # noqa: PLC0415

    seed = Path(args.seed_dir)
    claims = Path(args.claims_dir)
    summaries: list[dict[str, Any]] = []
    t0 = time.time()

    s = porb.run(args.porb_xlsx, args.porb_program, str(claims / "seed-porb.jsonl"),
                 str(seed / "porb_sp01.json"), str(seed / "prms_sp01_results.json"))
    summaries.append({**s, "seconds": round(time.time() - t0, 1)})

    t = time.time()
    s = prms.run(args.prms_db, args.program, args.limit, str(claims / "seed-prms.jsonl"),
                 str(seed / "prms_sp01_results.json"), args.registry,
                 str(seed / "porb_sp01.json"))
    summaries.append({**s, "seconds": round(time.time() - t, 1)})

    # PORB again: now that the PRMS extract exists, PORB partner names can be matched to CLARISA
    t = time.time()
    s = porb.run(args.porb_xlsx, args.porb_program, str(claims / "seed-porb.jsonl"),
                 str(seed / "porb_sp01.json"), str(seed / "prms_sp01_results.json"))
    summaries[0] = {**s, "seconds": round(summaries[0]["seconds"] + time.time() - t, 1)}

    t = time.time()
    s = cgspace.run(args.registry, args.porb_program, args.limit,
                    str(seed / "prms_sp01_results.json"), str(claims / "seed-cgspace.jsonl"),
                    str(seed / "cgspace_sp01_items.json"))
    summaries.append({**s, "seconds": round(time.time() - t, 1)})

    t = time.time()
    s = toc.run(str(seed / "porb_sp01.json"), args.registry, str(claims / "seed-toc.jsonl"),
                str(seed / "toc_sp01.json"), args.porb_xlsx)
    summaries.append({**s, "seconds": round(time.time() - t, 1)})

    t = time.time()
    s = taxonomy.run(args.taxonomy_base, [str(claims / "seed-*.jsonl")],
                     str(claims / "seed-taxonomy.jsonl"), str(seed / "taxonomy_v0.2.0.json"),
                     refresh_vendor=not args.no_refresh_vendor)
    summaries.append({**s, "seconds": round(time.time() - t, 1)})

    # --- summary table ----------------------------------------------------------------
    total_claims = sum(x["claims"] for x in summaries)
    objects: dict[str, int] = {}
    links: dict[str, int] = {}
    for x in summaries:
        for k, v in (x.get("objects") or {}).items():
            objects[k] = objects.get(k, 0) + v
        for k, v in (x.get("links") or {}).items():
            links[k] = links.get(k, 0) + v

    width = 100
    print("\n" + "=" * width)
    print(f"{'channel':<10}{'claims':>8}{'objects':>9}{'links':>8}{'sec':>7}  file")
    print("-" * width)
    for x in summaries:
        print(f"{x['channel']:<10}{x['claims']:>8}{sum((x.get('objects') or {}).values()):>9}"
              f"{sum((x.get('links') or {}).values()):>8}{x['seconds']:>7}  {x['out']}")
    print("-" * width)
    print(f"{'TOTAL':<10}{total_claims:>8}{sum(objects.values()):>9}{sum(links.values()):>8}"
          f"{round(time.time() - t0, 1):>7}")
    print("=" * width)
    print("objects by type:")
    for k, v in sorted(objects.items(), key=lambda kv: -kv[1]):
        print(f"   {k:<18}{v:>6}")
    print("links by predicate:")
    for k, v in sorted(links.items(), key=lambda kv: -kv[1]):
        print(f"   {k:<18}{v:>6}")
    print(f"\nunique object ids across batches: {_unique_objects(claims)}")
    print(f"total elapsed: {round(time.time() - t0, 1)}s")
    return 0


def _unique_objects(claims_dir: Path) -> int:
    from ingest import common  # noqa: PLC0415
    ids: set[str] = set()
    for f in sorted(claims_dir.glob("seed-*.jsonl")):
        for c in common.read_batch(f):
            if c["kind"] in ("assert_object", "candidate_concept"):
                ids.add(c["payload"]["id"])
    return len(ids)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="TRACE ingest CLI")
    sub = ap.add_subparsers(dest="command", required=True)
    a = sub.add_parser("all", help="run every intake channel with the default paths")
    a.add_argument("--prms-db", default="/Users/smithai/workspace/coding/PRMSDB/"
                                        "fresh_20260913/prdb_20260913.sqlite")
    a.add_argument("--registry", default="/Users/smithai/workspace/weai-local-corpus/data/registry.db")
    a.add_argument("--porb-xlsx", default="/Users/smithai/workspace/PORBs_consolidation/"
                                          "SummaryPORBs_v3/PORB_MASTER_All_Programs_13Aug2026.xlsx")
    a.add_argument("--program", default="SP01")
    a.add_argument("--porb-program", default="Breeding for Tomorrow")
    a.add_argument("--limit", type=int, default=50)
    a.add_argument("--seed-dir", default="data/seed")
    a.add_argument("--claims-dir", default="data/claims")
    a.add_argument("--taxonomy-base", default="http://localhost:8420")
    a.add_argument("--no-refresh-vendor", action="store_true")
    a.add_argument("--anchor", default=DEFAULT_ANCHOR,
                   help="frozen created_at for reproducible batches")
    a.add_argument("--live-time", action="store_true",
                   help="stamp claims with the real clock instead of the anchor")
    ns = ap.parse_args(argv)
    if ns.command == "all":
        return run_all(ns)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Fetch registered primary sources into content-addressed local snapshots."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from airspace.regulatory import ingest_source, utc_now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", help="Registered source ID; repeat to select several")
    parser.add_argument("--storage", type=Path, default=ROOT / "sources" / "snapshots")
    parser.add_argument("--catalogue", type=Path, default=ROOT / "sources" / "catalogue.json")
    args = parser.parse_args()
    catalogue = json.loads(args.catalogue.read_text(encoding="utf-8"))
    selected = [s for s in catalogue["sources"] if not args.source or s["id"] in args.source]
    results = []
    for source in selected:
        try:
            outcome = ingest_source(source, args.storage)
            outcome.pop("passages", None)
            results.append({"source_id": source["id"], "outcome": "Ingested", "manifest": outcome})
        except Exception as error:
            results.append({"source_id": source["id"], "outcome": "Failed", "checked_at": utc_now(), "error": str(error)})
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)
    args.storage.mkdir(parents=True, exist_ok=True)
    report = {"checked_at": utc_now(), "results": results}
    encoded = json.dumps(report, indent=2)
    checks = args.storage / "checks"
    checks.mkdir(exist_ok=True)
    stamp = report["checked_at"].replace(":", "-")
    (checks / (stamp + ".json")).write_text(encoded, encoding="utf-8")
    (args.storage / "last-check.json").write_text(encoded, encoding="utf-8")
    return 1 if any(r["outcome"] == "Failed" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

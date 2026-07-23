#!/usr/bin/env python3
"""Lint an AURORA import package (structure + engine import + quick stats).

  PYTHONPATH=backend python scripts/lint_package.py examples/real_mini_package.json
  PYTHONPATH=backend python scripts/lint_package.py cases/multisource-iron-air/package.json --json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("package", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="Fail on any import_errors")
    args = ap.parse_args(argv)

    sys.path.insert(0, str(ROOT / "backend"))
    from aurora import import_package
    from aurora.models import SOURCE_TYPES, ENTITY_TYPES, OBSERVATION_TYPES

    raw = json.loads(args.package.read_text(encoding="utf-8"))
    report = {
        "path": str(args.package),
        "ok": True,
        "issues": [],
        "counts": {},
        "source_types": {},
        "observation_types": {},
        "entity_types": {},
        "entities_with_external_ids": 0,
        "import_errors": 0,
    }

    for key in ("entities", "sources", "observations"):
        if key not in raw or not isinstance(raw.get(key), list):
            report["issues"].append(f"missing or non-array top-level key: {key}")
            report["ok"] = False

    if not report["ok"]:
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            for i in report["issues"]:
                print(f"FAIL {i}")
        return 1

    # vocab lint (soft)
    for i, e in enumerate(raw.get("entities") or []):
        et = e.get("entity_type")
        if et and et not in ENTITY_TYPES:
            report["issues"].append(f"entities[{i}] unknown entity_type {et}")
    for i, s in enumerate(raw.get("sources") or []):
        st = s.get("source_type")
        if st and st not in SOURCE_TYPES:
            report["issues"].append(f"sources[{i}] unknown source_type {st}")
    for i, o in enumerate(raw.get("observations") or []):
        ot = o.get("observation_type")
        if ot and ot not in OBSERVATION_TYPES:
            report["issues"].append(f"observations[{i}] unknown observation_type {ot}")

    pkg = {
        "entities": raw.get("entities") or [],
        "sources": raw.get("sources") or [],
        "observations": raw.get("observations") or [],
    }
    snap = import_package(pkg)
    report["import_errors"] = len(snap.import_errors or [])
    report["counts"] = dict(snap.counts)
    report["source_types"] = dict(Counter(s.source_type for s in snap.sources))
    report["observation_types"] = dict(
        Counter(o.observation_type for o in snap.observations)
    )
    report["entity_types"] = dict(Counter(e.entity_type for e in snap.entities))
    report["entities_with_external_ids"] = sum(
        1 for e in snap.entities if e.external_ids
    )
    if args.strict and report["import_errors"]:
        report["ok"] = False
        report["issues"].append(f"{report['import_errors']} import_errors")
    if report["issues"] and any("unknown" in i for i in report["issues"]):
        report["ok"] = False

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"package: {args.package}")
        print(f"  counts: {report['counts']}")
        print(f"  source_types: {report['source_types']}")
        print(f"  observation_types: {report['observation_types']}")
        print(
            f"  entities_with_external_ids: {report['entities_with_external_ids']}/"
            f"{report['counts'].get('entities', 0)}"
        )
        print(f"  import_errors: {report['import_errors']}")
        for i in report["issues"][:20]:
            print(f"  ISSUE: {i}")
        print("OK" if report["ok"] else "FAIL")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

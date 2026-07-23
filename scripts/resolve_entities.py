#!/usr/bin/env python3
"""Dry-run entity resolution against an import package.

Examples:
  PYTHONPATH=backend python scripts/resolve_entities.py cases/iron-air-retro/package.json \\
      --ref "FerroGrid Power"
  PYTHONPATH=backend python scripts/resolve_entities.py pkg.json --ref "ext:lei:LEI-FERRO"
  PYTHONPATH=backend python scripts/resolve_entities.py pkg.json --ref Delta --ext lei:D2
  PYTHONPATH=backend python scripts/resolve_entities.py pkg.json --list-external
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("package", type=Path, help="Import package JSON")
    ap.add_argument(
        "--ref",
        action="append",
        default=[],
        help="Name, ext:system:id, or system:id (repeatable)",
    )
    ap.add_argument(
        "--ext",
        action="append",
        default=[],
        help="Extra external id as system:id for disambiguation (repeatable)",
    )
    ap.add_argument(
        "--list-external",
        action="store_true",
        help="Print all entity external_ids in the package",
    )
    ap.add_argument("--json", action="store_true", help="Machine-readable output")
    args = ap.parse_args(argv)

    sys.path.insert(0, str(ROOT / "backend"))
    from aurora import import_package
    from aurora.entity_resolution import (
        EntityResolver,
        normalize_external_id,
        parse_entity_ref,
    )

    raw = json.loads(args.package.read_text(encoding="utf-8"))
    snap = import_package({
        "entities": raw.get("entities") or [],
        "sources": raw.get("sources") or [],
        "observations": raw.get("observations") or [],
    })
    resolver = EntityResolver(snap.entities)
    by_id = {e.entity_id: e for e in snap.entities}

    if args.list_external:
        rows = []
        for e in sorted(snap.entities, key=lambda x: x.entity_id):
            for x in e.external_ids or []:
                rows.append({
                    "entity_id": e.entity_id,
                    "canonical_name": e.canonical_name,
                    "system": x.get("system"),
                    "id": x.get("id"),
                })
        if args.json:
            print(json.dumps(rows, indent=2, ensure_ascii=False))
        else:
            for r in rows:
                print(f"{r['system']}:{r['id']}\t{r['canonical_name']}\t{r['entity_id']}")
        return 0

    if not args.ref:
        print("provide --ref and/or --list-external", file=sys.stderr)
        return 2

    extra = []
    for e in args.ext:
        k = normalize_external_id(e)
        if k:
            extra.append({"system": k[0], "id": k[1]})

    results = []
    for ref in args.ref:
        name, ext = parse_entity_ref(ref)
        eid = resolver.resolve(name, external_ids=list(ext) + extra)
        ent = by_id.get(eid) if eid else None
        results.append({
            "ref": ref,
            "resolved": eid is not None,
            "entity_id": eid,
            "canonical_name": ent.canonical_name if ent else None,
            "external_ids": list(ent.external_ids or []) if ent else [],
            "aliases": list(ent.aliases or []) if ent else [],
        })

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for r in results:
            if r["resolved"]:
                print(f"OK  {r['ref']!r} -> {r['canonical_name']} ({r['entity_id']})")
                if r["external_ids"]:
                    print(f"    external_ids={r['external_ids']}")
            else:
                print(f"MISS {r['ref']!r}")
    return 0 if all(r["resolved"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

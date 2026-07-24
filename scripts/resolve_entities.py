#!/usr/bin/env python3
"""Dry-run entity resolution against an import package.

Examples:
  PYTHONPATH=backend python scripts/resolve_entities.py cases/iron-air-retro/package.json \\
      --ref "FerroGrid Power"
  PYTHONPATH=backend python scripts/resolve_entities.py pkg.json --ref "ext:lei:LEI-FERRO"
  PYTHONPATH=backend python scripts/resolve_entities.py pkg.json --ref Delta --ext lei:D2
  PYTHONPATH=backend python scripts/resolve_entities.py pkg.json --list-external
  PYTHONPATH=backend python scripts/resolve_entities.py pkg.json --list-provisional
  PYTHONPATH=backend python scripts/resolve_entities.py pkg.json \\
      --promote "Mystery Corp" --to-type COMPANY -o promoted.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]


def _pkg_for_import(raw: dict) -> dict:
    """Build import_package input preserving stage_unresolved flags (0.1.39+)."""
    pkg: Dict[str, Any] = {
        "entities": list(raw.get("entities") or []),
        "sources": list(raw.get("sources") or []),
        "observations": list(raw.get("observations") or []),
    }
    if raw.get("documents"):
        pkg["documents"] = list(raw["documents"])
    for flag in ("license", "stage_unresolved", "stage_unresolved_subjects", "provisional_entity_type"):
        if flag in raw:
            pkg[flag] = raw[flag]
    if isinstance(raw.get("package"), dict):
        pkg["package"] = dict(raw["package"])
    if isinstance(raw.get("meta"), dict):
        pkg["meta"] = dict(raw["meta"])
    return pkg


def _is_provisional_entity(e) -> bool:
    return e.entity_type == "PROVISIONAL" or bool((e.metadata or {}).get("provisional"))


def _normalize_name(name: str) -> str:
    from aurora.ids import normalize_text

    return normalize_text(name)


def promote_raw_package(
    raw: dict,
    *,
    name: str,
    entity_type: str,
    also_clear_stage_flag: bool = False,
) -> dict:
    """Rewrite raw package: ensure entity row with name has entity_type (not provisional).

    Used to graduate staged / PROVISIONAL mentions into real types before re-import.
    """
    from aurora.models import ENTITY_TYPES

    if entity_type not in ENTITY_TYPES:
        raise ValueError(f"unknown entity_type {entity_type!r}; choose from {ENTITY_TYPES}")

    out = json.loads(json.dumps(raw))  # deep copy via JSON
    entities: List[dict] = list(out.get("entities") or [])
    target = _normalize_name(name)
    found = False
    for e in entities:
        if not isinstance(e, dict):
            continue
        cname = e.get("canonical_name") or ""
        aliases = e.get("aliases") or []
        names = [cname] + list(aliases)
        if any(_normalize_name(str(n)) == target for n in names if n):
            e["entity_type"] = entity_type
            meta = dict(e.get("metadata") or {})
            meta.pop("provisional", None)
            e["metadata"] = meta
            # prefer setting canonical to the promoted surface form when it was only an alias
            if _normalize_name(str(cname)) != target and name:
                if cname and cname not in aliases:
                    aliases = list(aliases) + [cname]
                    e["aliases"] = aliases
                e["canonical_name"] = name
            found = True
    if not found:
        entities.append({
            "entity_type": entity_type,
            "canonical_name": name,
            "aliases": [],
            "metadata": {},
        })
    out["entities"] = entities
    if also_clear_stage_flag:
        out.pop("stage_unresolved", None)
        out.pop("stage_unresolved_subjects", None)
        if isinstance(out.get("package"), dict):
            out["package"].pop("stage_unresolved", None)
            out["package"].pop("stage_unresolved_subjects", None)
    return out


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
    ap.add_argument(
        "--list-provisional",
        action="store_true",
        help="List provisional entities after import (type PROVISIONAL / metadata.provisional; 0.1.40+)",
    )
    ap.add_argument(
        "--promote",
        action="append",
        default=[],
        metavar="NAME",
        help="Promote provisional (or missing) entity NAME to --to-type; rewrite package (0.1.40+)",
    )
    ap.add_argument(
        "--to-type",
        default="COMPANY",
        help="entity_type for --promote (default COMPANY)",
    )
    ap.add_argument(
        "--clear-stage-flag",
        action="store_true",
        help="With --promote, also remove package stage_unresolved flags",
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write promoted package JSON here (default: stdout when promoting)",
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
    from aurora.models import ENTITY_TYPES

    raw = json.loads(args.package.read_text(encoding="utf-8"))

    # --- promote (raw package rewrite; does not require resolve success) ---
    if args.promote:
        if args.to_type not in ENTITY_TYPES:
            print(
                f"unknown --to-type {args.to_type!r}; valid: {', '.join(ENTITY_TYPES)}",
                file=sys.stderr,
            )
            return 2
        out_pkg = raw
        promoted = []
        for name in args.promote:
            out_pkg = promote_raw_package(
                out_pkg,
                name=name,
                entity_type=args.to_type,
                also_clear_stage_flag=args.clear_stage_flag,
            )
            promoted.append({"name": name, "entity_type": args.to_type})
        text = json.dumps(out_pkg, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            args.output.write_text(text, encoding="utf-8")
            if args.json:
                print(json.dumps({"ok": True, "output": str(args.output), "promoted": promoted}, indent=2))
            else:
                print(f"wrote {args.output} ({len(promoted)} promote(s) → {args.to_type})")
        else:
            # package on stdout; status on stderr when not --json
            if args.json:
                print(json.dumps({"ok": True, "promoted": promoted, "package": out_pkg}, indent=2, ensure_ascii=False))
            else:
                sys.stdout.write(text)
        return 0

    snap = import_package(_pkg_for_import(raw))
    resolver = EntityResolver(snap.entities)
    by_id = {e.entity_id: e for e in snap.entities}

    if args.list_provisional:
        rows = []
        for e in sorted(snap.entities, key=lambda x: x.entity_id):
            if not _is_provisional_entity(e):
                continue
            rows.append({
                "entity_id": e.entity_id,
                "canonical_name": e.canonical_name,
                "entity_type": e.entity_type,
                "provisional": True,
                "external_ids": list(e.external_ids or []),
                "aliases": list(e.aliases or []),
            })
        if args.json:
            print(json.dumps(rows, indent=2, ensure_ascii=False))
        else:
            if not rows:
                print("(no provisional entities)")
            for r in rows:
                print(
                    f"PROVISIONAL\t{r['canonical_name']}\t{r['entity_type']}\t{r['entity_id']}"
                )
        return 0

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
        print(
            "provide --ref and/or --list-external / --list-provisional / --promote",
            file=sys.stderr,
        )
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
            "entity_type": ent.entity_type if ent else None,
            "provisional": _is_provisional_entity(ent) if ent else False,
            "external_ids": list(ent.external_ids or []) if ent else [],
            "aliases": list(ent.aliases or []) if ent else [],
        })

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for r in results:
            if r["resolved"]:
                flag = " [provisional]" if r["provisional"] else ""
                print(
                    f"OK  {r['ref']!r} -> {r['canonical_name']} "
                    f"({r['entity_type']}) ({r['entity_id']}){flag}"
                )
                if r["external_ids"]:
                    print(f"    external_ids={r['external_ids']}")
            else:
                print(f"MISS {r['ref']!r}")
    return 0 if all(r["resolved"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

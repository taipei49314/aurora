#!/usr/bin/env python3
"""Validate an AURORA import package.

Checks:
  1. JSON parse
  2. Optional JSON Schema (examples/schemas/import-package.schema.json)
  3. Engine import_package() success + summary counts
  4. Optional discovery run against the bundled taxonomy

Usage:
  PYTHONPATH=backend python scripts/validate_package.py examples/real_mini_package.json
  PYTHONPATH=backend python scripts/validate_package.py examples/real_mini_package.json --run
  PYTHONPATH=backend python scripts/validate_package.py examples/real_mini_package.json --schema-only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "examples" / "schemas" / "import-package.schema.json"
TAXONOMY_PATH = ROOT / "datasets" / "taxonomy" / "taxonomy.json"


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: top-level value must be a JSON object")
    return data


def validate_schema(raw: dict) -> list[str]:
    """Return a list of schema error strings (empty if ok or jsonschema missing)."""
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return ["[skip] jsonschema not installed; structural schema check skipped"]

    schema = _load_json(SCHEMA_PATH)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(raw), key=lambda e: list(e.path))
    out = []
    for err in errors:
        loc = ".".join(str(p) for p in err.path) or "<root>"
        out.append(f"[schema] {loc}: {err.message}")
    return out


def validate_engine(raw: dict) -> dict:
    sys.path.insert(0, str(ROOT / "backend"))
    from aurora import import_package  # noqa: WPS433

    # Strip documentation-only keys that adapters may include
    package = {
        "entities": raw.get("entities", []),
        "sources": raw.get("sources", []),
        "observations": raw.get("observations", []),
    }
    snap = import_package(package)
    row_errors = list(snap.import_errors or [])
    return {
        "snapshot_id": snap.snapshot_id,
        "counts": dict(snap.counts),
        "n_entities": len(snap.entities),
        "n_sources": len(snap.sources),
        "n_observations": len(snap.observations),
        "import_errors": row_errors,
    }


def run_pipeline(snapshot) -> dict:
    sys.path.insert(0, str(ROOT / "backend"))
    from aurora import DEFAULT_CONFIG, Taxonomy, run_pipeline  # noqa: WPS433

    taxonomy = Taxonomy.load(TAXONOMY_PATH)
    run = run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG, cutoff_date=None)
    statuses = {}
    for h in run.hypotheses:
        statuses[h.status] = statuses.get(h.status, 0) + 1
    top = sorted(run.hypotheses, key=lambda h: -h.overall_score)[:8]
    return {
        "run_id": run.run_id,
        "n_hypotheses": len(run.hypotheses),
        "status_counts": statuses,
        "top": [
            {
                "status": h.status,
                "overall": round(h.overall_score, 1),
                "name": h.generated_name,
            }
            for h in top
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="Path to import package JSON")
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help="Only run JSON Schema validation (requires jsonschema)",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Also execute discovery pipeline on the imported snapshot",
    )
    parser.add_argument(
        "--strict-errors",
        action="store_true",
        help="Exit non-zero if import_package reports any row-level errors",
    )
    args = parser.parse_args(argv)

    path = args.package
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2

    raw = _load_json(path)
    print(f"package: {path}")
    print(
        f"  rows: entities={len(raw.get('entities', []))} "
        f"sources={len(raw.get('sources', []))} "
        f"observations={len(raw.get('observations', []))}"
    )

    schema_msgs = validate_schema(raw)
    schema_hard_fail = False
    for msg in schema_msgs:
        print(f"  {msg}")
        if msg.startswith("[schema]"):
            schema_hard_fail = True
    if schema_hard_fail:
        print("FAIL: JSON Schema validation")
        return 1
    if args.schema_only:
        if any(m.startswith("[skip]") for m in schema_msgs):
            print("WARN: schema-only requested but jsonschema missing")
            return 2
        print("OK: JSON Schema")
        return 0

    try:
        result = validate_engine(raw)
    except Exception as exc:  # noqa: BLE001 — CLI surface
        print(f"FAIL: import_package raised {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"  snapshot_id: {result['snapshot_id']}")
    print(
        f"  imported: entities={result['n_entities']} "
        f"sources={result['n_sources']} observations={result['n_observations']}"
    )
    print(f"  counts: {result['counts']}")
    n_err = len(result["import_errors"])
    print(f"  import_errors: {n_err}")
    for err in result["import_errors"][:20]:
        print(f"    - {err}")
    if n_err > 20:
        print(f"    ... and {n_err - 20} more")

    if args.strict_errors and n_err:
        print("FAIL: row-level import errors present (--strict-errors)")
        return 1

    if args.run:
        sys.path.insert(0, str(ROOT / "backend"))
        from aurora import import_package  # noqa: WPS433

        package = {
            "entities": raw.get("entities", []),
            "sources": raw.get("sources", []),
            "observations": raw.get("observations", []),
        }
        snap = import_package(package)
        try:
            run_info = run_pipeline(snap)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: pipeline raised {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        print(f"  run_id: {run_info['run_id']}")
        print(f"  hypotheses: {run_info['n_hypotheses']}  statuses={run_info['status_counts']}")
        for row in run_info["top"]:
            print(f"    {row['status']:28} {row['overall']:5.1f}  {row['name']}")

    # Soft success if we imported at least one observation without hard exception
    if result["n_observations"] == 0 and len(raw.get("observations", [])) > 0:
        print("FAIL: all observations dropped")
        return 1

    print("OK: package imports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

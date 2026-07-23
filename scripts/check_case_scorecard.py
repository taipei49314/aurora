#!/usr/bin/env python3
"""Check a case package against its scorecard.json gates."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "case_dir",
        type=Path,
        nargs="?",
        default=ROOT / "cases" / "iron-air-mini",
    )
    args = p.parse_args(argv)
    case_dir = args.case_dir
    scorecard = json.loads((case_dir / "scorecard.json").read_text(encoding="utf-8"))
    package = json.loads((case_dir / "package.json").read_text(encoding="utf-8"))
    gates = scorecard["gates"]

    sys.path.insert(0, str(ROOT / "backend"))
    from aurora import import_package

    snap = import_package({
        "entities": package.get("entities", []),
        "sources": package.get("sources", []),
        "observations": package.get("observations", []),
    })
    n_err = len(snap.import_errors or [])
    obs_types = {o.observation_type for o in snap.observations}
    raw = snap.counts.get("raw_source_count", 0)
    indep = snap.counts.get("independent_source_count", 0)

    failures = []
    if n_err > gates.get("import_errors_max", 0):
        failures.append(f"import_errors={n_err} > max {gates['import_errors_max']}")
    for t in gates.get("require_observation_types", []):
        if t not in obs_types:
            failures.append(f"missing observation_type {t}")
    if gates.get("independent_lt_raw") and not (indep < raw):
        failures.append(f"expected independent ({indep}) < raw ({raw})")
    if raw < gates.get("min_sources", 0):
        failures.append(f"raw sources {raw} < min_sources {gates['min_sources']}")

    print(
        f"case={scorecard.get('case_id')} errors={n_err} "
        f"sources={raw} independent={indep} obs_types={sorted(obs_types)}"
    )
    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("OK: scorecard gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

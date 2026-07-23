#!/usr/bin/env python3
"""Run a retro case: cutoff pipelines + ledger gates + leakage checks.

Usage:
  PYTHONPATH=backend python scripts/run_retro_case.py cases/iron-air-retro
  PYTHONPATH=backend python scripts/run_retro_case.py cases/iron-air-retro --json-out cases/iron-air-retro/last_run.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]


def _load_case(case_dir: Path) -> dict:
    pkg_path = case_dir / "package.json"
    ledger_path = case_dir / "ledger.json"
    if not pkg_path.is_file():
        raise SystemExit(f"missing {pkg_path}")
    if not ledger_path.is_file():
        raise SystemExit(f"missing {ledger_path}")
    package = json.loads(pkg_path.read_text(encoding="utf-8"))
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    return {"package": package, "ledger": ledger, "case_dir": case_dir}


def _engine_package(raw: dict) -> dict:
    out = {
        "entities": raw.get("entities") or [],
        "sources": raw.get("sources") or [],
        "observations": raw.get("observations") or [],
    }
    if raw.get("documents"):
        out["documents"] = list(raw["documents"])
    return out


def _hyp_summary(run) -> List[dict]:
    rows = []
    for h in sorted(run.hypotheses, key=lambda x: -x.overall_score):
        rows.append({
            "status": h.status,
            "overall": round(h.overall_score, 2),
            "name": h.generated_name,
            "hype": round(h.hype_risk_score, 2),
            "entities": len(h.entity_ids),
        })
    return rows


def _check_cutoff(
    *,
    date: str,
    expect: dict,
    run,
    cutoff_manifest: dict,
    prior_best: Optional[float],
) -> List[str]:
    fails: List[str] = []
    hyps = _hyp_summary(run)
    best = hyps[0]["overall"] if hyps else 0.0
    best_status = hyps[0]["status"] if hyps else None
    statuses = {h["status"] for h in hyps}
    included = cutoff_manifest.get("included_observation_count", 0)

    # Leakage: pipeline already asserts; count future exclusions as health signal
    if expect.get("leakage_violations", 0) != 0:
        fails.append("ledger expects non-zero leakage_violations (unsupported)")

    for st in expect.get("forbid_any_status") or []:
        if st in statuses:
            fails.append(f"forbidden status present: {st}")

    if "max_best_overall" in expect and best > float(expect["max_best_overall"]):
        fails.append(
            f"best overall {best} > max_best_overall {expect['max_best_overall']}"
        )
    if "min_best_overall" in expect and best < float(expect["min_best_overall"]):
        # only enforce when at least one hypothesis exists
        if hyps:
            fails.append(
                f"best overall {best} < min_best_overall {expect['min_best_overall']}"
            )
        else:
            fails.append("no hypotheses but min_best_overall required")

    if "min_included_observations" in expect and included < int(
        expect["min_included_observations"]
    ):
        fails.append(
            f"included obs {included} < min {expect['min_included_observations']}"
        )
    if "max_included_observations" in expect and included > int(
        expect["max_included_observations"]
    ):
        fails.append(
            f"included obs {included} > max {expect['max_included_observations']}"
        )

    if expect.get("require_best_status_in") and best_status:
        allowed = set(expect["require_best_status_in"])
        if best_status not in allowed:
            fails.append(
                f"best status {best_status} not in {sorted(allowed)}"
            )

    if expect.get("improve_best_overall_vs") is not None and prior_best is not None:
        delta = best - prior_best
        min_delta = float(expect.get("min_overall_delta", 0))
        if delta < min_delta:
            fails.append(
                f"best overall delta {delta:.2f} < min_overall_delta {min_delta} "
                f"(prior={prior_best}, now={best})"
            )

    return fails


def run_case(case_dir: Path) -> dict:
    sys.path.insert(0, str(ROOT / "backend"))
    from aurora import DEFAULT_CONFIG, Taxonomy, import_package, run_pipeline
    from aurora import leakage as leakage_mod

    loaded = _load_case(case_dir)
    package = loaded["package"]
    ledger = loaded["ledger"]
    snap = import_package(_engine_package(package))
    tax = Taxonomy.load(ROOT / "datasets" / "taxonomy" / "taxonomy.json")

    report: Dict[str, Any] = {
        "case_id": ledger.get("case_id"),
        "snapshot_id": snap.snapshot_id,
        "import_errors": len(snap.import_errors or []),
        "full_counts": dict(snap.counts),
        "honesty": ledger.get("honesty"),
        "cutoffs": [],
        "failures": [],
        "passed": False,
    }

    if report["import_errors"]:
        report["failures"].append(f"import_errors={report['import_errors']}")

    # full-package independence gate
    g = ledger.get("global") or {}
    if g.get("require_independent_lt_raw_on_full"):
        raw = snap.counts.get("raw_source_count", 0)
        indep = snap.counts.get("independent_source_count", 0)
        if not (indep < raw):
            report["failures"].append(
                f"full package independent ({indep}) not < raw ({raw})"
            )

    best_by_cutoff: Dict[str, float] = {}
    leakage_total = 0

    for entry in ledger.get("cutoffs") or []:
        date = entry["date"]
        expect = entry.get("expect") or {}
        cut = leakage_mod.apply_cutoff(snap.observations, snap.sources, date)
        # explicit leakage re-check on included set
        try:
            leakage_mod.assert_no_leakage(cut["observations"], date)
            leak_v = 0
        except Exception as exc:  # noqa: BLE001
            leak_v = 1
            leakage_total += 1
            report["failures"].append(f"cutoff {date}: leakage {exc}")

        run = run_pipeline(snap, tax, DEFAULT_CONFIG, cutoff_date=date)
        hyps = _hyp_summary(run)
        best = hyps[0]["overall"] if hyps else 0.0
        best_by_cutoff[date] = best

        # type presence among *included* observations at cutoff
        included_types = {o.observation_type for o in cut["observations"]}
        type_req = expect.get("require_included_types_any") or []
        type_fail = []
        if type_req and not any(t in included_types for t in type_req):
            type_fail.append(
                f"none of required types {type_req} in included set {sorted(included_types)}"
            )

        prior_key = expect.get("improve_best_overall_vs")
        prior_best = best_by_cutoff.get(prior_key) if prior_key else None
        fails = _check_cutoff(
            date=date,
            expect=expect,
            run=run,
            cutoff_manifest=cut["manifest"],
            prior_best=prior_best,
        )
        fails.extend(type_fail)

        row = {
            "date": date,
            "label": entry.get("label"),
            "manifest": cut["manifest"],
            "leakage_violations": leak_v,
            "hypotheses": hyps,
            "best_overall": best,
            "included_types": sorted(included_types),
            "gate_failures": fails,
        }
        report["cutoffs"].append(row)
        for f in fails:
            report["failures"].append(f"cutoff {date}: {f}")

    if g.get("require_zero_leakage_all_cutoffs") and leakage_total:
        report["failures"].append(f"total leakage violations {leakage_total}")

    report["passed"] = len(report["failures"]) == 0
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "case_dir",
        type=Path,
        nargs="?",
        default=ROOT / "cases" / "iron-air-retro",
    )
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)

    report = run_case(args.case_dir)
    print(f"case={report['case_id']} snapshot={report['snapshot_id']}")
    print(f"import_errors={report['import_errors']} counts={report['full_counts']}")
    for h in report.get("honesty") or []:
        print(f"  honesty: {h}")
    print("-" * 72)
    for c in report["cutoffs"]:
        print(
            f"{c['date']}  included={c['manifest']['included_observation_count']:2d}  "
            f"future_excl={c['manifest']['excluded_future_observation_count']:2d}  "
            f"leak={c['leakage_violations']}  best={c['best_overall']:5.1f}"
        )
        for hyp in c["hypotheses"][:3]:
            print(
                f"    {hyp['status']:28} {hyp['overall']:5.1f}  hype={hyp['hype']:5.1f}  {hyp['name']}"
            )
        if not c["hypotheses"]:
            print("    (no hypotheses)")
        for f in c["gate_failures"]:
            print(f"    FAIL: {f}")
    print("-" * 72)
    if report["passed"]:
        print("OK: retro ledger gates passed")
    else:
        print("FAIL: retro ledger gates")
        for f in report["failures"]:
            print(f"  - {f}")

    out = args.json_out or (args.case_dir / "last_run.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

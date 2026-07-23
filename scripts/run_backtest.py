"""`make backtest` — historical discovery backtest over several cutoffs."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "datasets" / "northstar"))

import generate
from aurora import import_package, Taxonomy, DEFAULT_CONFIG
from aurora.backtest import run_backtest


def main():
    pkg, _ = generate.generate()
    snap = import_package(pkg)
    tax = Taxonomy.load(ROOT / "datasets" / "taxonomy" / "taxonomy.json")
    cutoffs = ["2020-12-31", "2021-12-31", "2022-12-31", "2023-12-31", "2024-12-31", "2025-06-30"]
    bt = run_backtest(snap, tax, cutoffs, DEFAULT_CONFIG)
    print(f"cutoffs: {bt['cutoffs']}")
    print(f"future_leakage_violations: {bt['future_leakage_violations']}")
    print(f"median_early_discovery_lead_days: {bt['median_early_discovery_lead_days']}")
    print(f"false_positive_candidates: {bt['false_positive_candidates']}")
    print("-" * 70)
    for t in bt["tracks"]:
        hist = " ".join(f"{s['cutoff'][:4]}:{s['status'][:4]}" for s in t["history"])
        print(f"{t['final_status']:<26} lead={str(t['early_discovery_lead_days']):>5}  {t['name'][:28]:<30} {hist}")


if __name__ == "__main__":
    main()

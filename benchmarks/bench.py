"""`make benchmark` — measure per-stage timing and data volume (spec §31).

Prints real, measured numbers (never a claimed fixed second count) for import
and each pipeline stage at a given corpus scale.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "datasets" / "northstar"))

import generate
from aurora import import_package, Taxonomy, run_pipeline, DEFAULT_CONFIG


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=1.0)
    args = ap.parse_args()

    t0 = time.perf_counter()
    pkg, _ = generate.generate(scale=args.scale)
    t_gen = time.perf_counter() - t0

    t0 = time.perf_counter()
    snap = import_package(pkg)
    t_import = time.perf_counter() - t0

    tax = Taxonomy.load(ROOT / "datasets" / "taxonomy" / "taxonomy.json")
    t0 = time.perf_counter()
    run = run_pipeline(snap, tax, DEFAULT_CONFIG)
    t_run = time.perf_counter() - t0

    print(f"scale={args.scale}")
    print(f"volume: entities={snap.counts['entities']} sources={snap.counts['sources']} "
          f"observations={snap.counts['observations']}")
    print(f"generate:        {t_gen*1000:8.1f} ms")
    print(f"import+dedup+ER: {t_import*1000:8.1f} ms")
    print(f"pipeline total:  {t_run*1000:8.1f} ms")
    print("pipeline stages (measured):")
    for stage, secs in run.stage_timings.items():
        print(f"  {stage:<14} {secs*1000:8.1f} ms")
    print(f"hypotheses: {len(run.hypotheses)}")


if __name__ == "__main__":
    main()

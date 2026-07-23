"""Command-line demo / runner (spec §32 `make demo`).

Generates (or loads) the Northstar corpus, imports it, runs the discovery
pipeline and prints a human-readable summary of classified hypotheses with the
key score components and evidence. No industry answer is hardcoded.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "datasets" / "northstar"))

from aurora import import_package, Taxonomy, run_pipeline, DEFAULT_CONFIG  # noqa: E402


def load_package(scale: float):
    import generate  # from datasets/northstar
    package, _gt = generate.generate(scale=scale)
    return package


def main(argv=None):
    ap = argparse.ArgumentParser(description="AURORA discovery demo")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--cutoff", default=None, help="cutoff date YYYY-MM-DD for a historical run")
    ap.add_argument("--taxonomy", default=str(ROOT / "datasets" / "taxonomy" / "taxonomy.json"))
    args = ap.parse_args(argv)

    package = load_package(args.scale)
    snap = import_package(package)
    tax = Taxonomy.load(args.taxonomy)
    run = run_pipeline(snap, tax, DEFAULT_CONFIG, cutoff_date=args.cutoff)

    print("=" * 78)
    print(f"AURORA run {run.run_id}")
    print(f"snapshot={snap.snapshot_id}  cutoff={run.cutoff_date}  engine={run.engine_version}")
    print(f"entities={snap.counts['entities']} sources={snap.counts['sources']} "
          f"observations={snap.counts['observations']}")
    print(f"raw_sources={snap.counts.get('raw_source_count')} "
          f"deduplicated={snap.counts.get('deduplicated_source_count')} "
          f"independent={snap.counts.get('independent_source_count')}")
    print(f"cluster_agreement(feature vs graph)={run.leakage_manifest.get('cluster_agreement')}")
    print(f"import_errors={snap.counts['import_errors']}  leakage={run.leakage_manifest}")
    print("-" * 78)
    print(f"{'STATUS':<28}{'OVERALL':>8}{'HYPE':>6}{'CONTRA':>7}{'SIM':>6}  NAME")
    for h in run.hypotheses:
        sim = h.existing_industry_similarity.get("similarity", 0)
        print(f"{h.status:<28}{h.overall_score:>8.1f}{h.hype_risk_score:>6.0f}"
              f"{h.contradiction_score:>7.0f}{sim:>6.2f}  {h.generated_name[:34]}")
    print("=" * 78)
    # top bottleneck across candidate/emerging clusters
    for h in run.hypotheses:
        bns = h.score_explanation.get("bottlenecks", [])
        if h.status in {"INDUSTRY_CANDIDATE", "EMERGING_CAPABILITY_CLUSTER"} and bns:
            top = bns[0]
            print(f"[bottleneck] {h.generated_name[:30]:<32} -> "
                  f"{top['entity_id']} score={top['bottleneck_score']} "
                  f"(centrality={top['centrality']}, substitutability={top['substitutability']})")
    return run


if __name__ == "__main__":
    main()

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


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="AURORA discovery demo")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--cutoff", default=None, help="cutoff date YYYY-MM-DD for a historical run")
    ap.add_argument("--taxonomy", default=str(ROOT / "datasets" / "taxonomy" / "taxonomy.json"))
    ap.add_argument(
        "--brain",
        metavar="VAULT",
        default=None,
        help="after the run, send the FINDING report into an md-brain Vault as an episodic proposal",
    )
    ap.add_argument(
        "--brain-bin",
        default=None,
        help="mdbrain binary (default: mdbrain on PATH)",
    )
    ap.add_argument(
        "--brain-report-dir",
        default=None,
        help="where to write the *.fleet.md report (default: ./reports)",
    )
    ap.add_argument(
        "--atlas",
        nargs="?",
        const="http://127.0.0.1:8000",
        default=None,
        metavar="URL",
        help="after the run, submit the FINDING report to Frontier Atlas (default http://127.0.0.1:8000)",
    )
    ap.add_argument(
        "--atlas-workspace",
        default="Fleet",
        help="Atlas workspace name (default Fleet)",
    )
    return ap


def cli_inputs(argv: list[str] | None = None) -> str:
    """Provenance string for Atlas / Vault. Prefer the argv actually parsed."""
    if argv is not None:
        return " ".join(str(item) for item in argv)
    return " ".join(sys.argv[1:])


def push_to_atlas(run, snapshot, args, *, inputs: str | None = None) -> None:
    """Submit observations to Atlas. A failed push never fails the research run.

    The demo CLI does not invent a retention baseline. Findings still land;
    predictions are skipped until a measured backtest is supplied separately.
    """
    from aurora import atlas

    try:
        pushed = atlas.push_run(
            run,
            snapshot,
            base_url=args.atlas,
            workspace=args.atlas_workspace,
            inputs=cli_inputs() if inputs is None else inputs,
        )
    except atlas.AtlasError as exc:
        print(f"\n[atlas] submit failed: {exc}", file=sys.stderr)
        print("The research run itself completed; retry later.", file=sys.stderr)
        return
    print(
        f"\n[atlas] submitted {pushed['findings']} findings"
        f" (run {str(pushed.get('module_run_id') or '')[:8]}, "
        f"hash {str(pushed.get('report_hash') or '')[:12]})."
    )
    skipped = pushed.get("predictions_skipped_reason")
    if skipped:
        print(f"[atlas] predictions skipped: {skipped}")
    else:
        print(f"[atlas] registered {len(pushed.get('predictions') or [])} prediction(s).")
    print("Atlas claims stay unreviewed until a human accepts them.")


def push_to_brain(run, snapshot, args, *, inputs: str | None = None) -> None:
    """Send experience to md-brain. A failed ingest never fails the research run."""
    from aurora import brain

    try:
        pushed = brain.ingest_run(
            run,
            snapshot,
            vault=args.brain,
            mdbrain_bin=args.brain_bin,
            report_dir=args.brain_report_dir,
            inputs=cli_inputs() if inputs is None else inputs,
        )
    except brain.BrainError as exc:
        print(f"\n[brain] Vault ingest failed: {exc}", file=sys.stderr)
        print("The research run itself completed; retry with mdbrain ingest.", file=sys.stderr)
        return
    print(
        f"\n[brain] opened proposal {pushed['proposal_id']}"
        f" ({pushed.get('status') or 'proposed'}, {pushed.get('target_path') or '—'})."
    )
    print("This is an experience draft, not an Atlas claim; approve it before memory/episodic/.")


def main(argv=None):
    args = build_parser().parse_args(argv)

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
    inputs = cli_inputs(argv)
    if args.atlas:
        push_to_atlas(run, snap, args, inputs=inputs)
    if args.brain:
        push_to_brain(run, snap, args, inputs=inputs)
    return run


if __name__ == "__main__":
    main()

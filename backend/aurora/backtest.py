"""Historical discovery backtest (spec §20).

Sweep a series of cutoff dates, run the pipeline at each using only data
available then (leakage-checked), and track how each cluster's status evolves.
We then measure early-discovery lead time and false positives against the
full-data run — WITHOUT ever pasting today's known industry names back onto the
past (spec §20 last line): "candidate" status is derived purely from the
engine's own historical output.

Clusters are matched across cutoffs by entity-set Jaccard, so a cluster that
grows or drifts is still tracked as the same latent field.
"""
from __future__ import annotations

from datetime import date

from .config import EngineConfig, DEFAULT_CONFIG
from .pipeline import run_pipeline
from . import leakage

_EMERGING = {"EMERGING_CAPABILITY_CLUSTER", "INDUSTRY_CANDIDATE"}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def run_backtest(snapshot, taxonomy, cutoffs, cfg: EngineConfig = DEFAULT_CONFIG) -> dict:
    cutoffs = sorted(cutoffs)
    per_cutoff = []
    for c in cutoffs:
        run = run_pipeline(snapshot, taxonomy, cfg, cutoff_date=c)
        # hard leakage check for every historical run
        leakage.assert_no_leakage(
            leakage.apply_cutoff(snapshot.observations, snapshot.sources, c)["observations"], c)
        per_cutoff.append({
            "cutoff": c,
            "clusters": [{"entities": set(h.entity_ids), "status": h.status,
                          "name": h.generated_name, "overall": h.overall_score} for h in run.hypotheses],
            "leakage_manifest": run.leakage_manifest,
        })

    # full-data reference run
    full = run_pipeline(snapshot, taxonomy, cfg, cutoff_date=None)
    tracks = []
    for h in full.hypotheses:
        eset = set(h.entity_ids)
        history = []
        for pc in per_cutoff:
            best = max(pc["clusters"], key=lambda c: _jaccard(eset, c["entities"]), default=None)
            match = best if best and _jaccard(eset, best["entities"]) >= 0.4 else None
            history.append({"cutoff": pc["cutoff"], "status": match["status"] if match else "ABSENT",
                            "overall": match["overall"] if match else None})
        first_emerging = next((s["cutoff"] for s in history if s["status"] in _EMERGING), None)
        first_candidate = next((s["cutoff"] for s in history if s["status"] == "INDUSTRY_CANDIDATE"), None)
        lead_days = None
        if first_emerging and h.status == "INDUSTRY_CANDIDATE":
            fe = date.fromisoformat(first_emerging)
            # lead time relative to when the engine (on full data) is confident:
            # use the last cutoff / final classification as the "market-known"
            # reference point.
            ref = date.fromisoformat(cutoffs[-1])
            lead_days = (ref - fe).days
        tracks.append({
            "final_status": h.status, "name": h.generated_name,
            "final_overall": h.overall_score, "history": history,
            "first_emerging_cutoff": first_emerging, "first_candidate_cutoff": first_candidate,
            "early_discovery_lead_days": lead_days,
        })

    # metrics
    leads = sorted(t["early_discovery_lead_days"] for t in tracks if t["early_discovery_lead_days"])
    median_lead = leads[len(leads) // 2] if leads else None
    false_positives = [t["name"] for t in tracks
                       if t["final_status"] in {"HYPE_CLUSTER", "REJECTED", "INSUFFICIENT_EVIDENCE"}
                       and any(s["status"] == "INDUSTRY_CANDIDATE" for s in t["history"])]
    return {
        "cutoffs": cutoffs,
        "tracks": tracks,
        "median_early_discovery_lead_days": median_lead,
        "false_positive_candidates": false_positives,
        "future_leakage_violations": 0,  # would have raised above otherwise
    }

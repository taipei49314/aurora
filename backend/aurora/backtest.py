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

import hashlib
import json
from datetime import date
from typing import Any

from .config import EngineConfig, DEFAULT_CONFIG
from .pipeline import run_pipeline
from . import leakage

_EMERGING = {"EMERGING_CAPABILITY_CLUSTER", "INDUSTRY_CANDIDATE"}
BACKTEST_MANIFEST_SCHEMA = "aurora-backtest-manifest/v1"
_LINEAGE_REFERENCE_FIELDS = (
    "schema_version",
    "dataset_id",
    "dataset_version",
    "artifact_sha256",
    "manifest_sha256",
)


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _sha256_reference(value: Any) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json_bytes(value)).hexdigest()}"


def _lineage_items(lineage: Any):
    if not isinstance(lineage, dict):
        return
    if lineage.get("schema_version") == "aurora-package-lineage/v1":
        for item in lineage.get("datasets") or []:
            yield from _lineage_items(item)
        return
    yield lineage


def corpus_lineage_references(snapshot) -> list[dict]:
    """Return sorted, digest-focused corpus references found on snapshot rows.

    Offline adapters stamp compact lineage into row metadata. Backtests retain
    only identity fields and artifact/manifest digests here, avoiding copies of
    mutable URLs, license prose, or retrieval descriptions.
    """
    references: dict[str, dict] = {}
    for collection in (
        snapshot.entities,
        snapshot.sources,
        snapshot.observations,
        getattr(snapshot, "documents", None) or [],
    ):
        for row in collection:
            metadata = getattr(row, "metadata", None) or {}
            if not isinstance(metadata, dict):
                continue
            lineage_values = [
                metadata.get("corpus_lineage"),
                metadata.get("package_lineage"),
            ]
            aliases = metadata.get("provenance_aliases")
            if isinstance(aliases, list):
                for alias in aliases:
                    if not isinstance(alias, dict):
                        continue
                    alias_metadata = alias.get("metadata")
                    if isinstance(alias_metadata, dict):
                        lineage_values.append(alias_metadata.get("corpus_lineage"))
                        lineage_values.append(alias_metadata.get("package_lineage"))
            for lineage in lineage_values:
                for item in _lineage_items(lineage):
                    reference = {
                        field: item[field]
                        for field in _LINEAGE_REFERENCE_FIELDS
                        if item.get(field) not in (None, "")
                    }
                    if not reference:
                        continue
                    key = _canonical_json_bytes(reference).decode("utf-8")
                    references[key] = reference
    return [references[key] for key in sorted(references)]


def _run_reference(run) -> dict:
    return {
        "cutoff": run.cutoff_date,
        "run_id": run.run_id,
        "input_manifest_hash": run.input_manifest_hash,
        "result_manifest_hash": run.result_manifest_hash,
        "leakage_manifest": dict(run.leakage_manifest or {}),
    }


def build_backtest_manifest(
    snapshot,
    cfg: EngineConfig,
    cutoffs,
    cutoff_runs,
    full_run,
) -> dict:
    """Build the deterministic audit manifest used to identify a backtest.

    Runtime-only values such as ResearchRun.created_at and stage timings are
    deliberately excluded. The manifest is therefore stable across equivalent
    replays while still binding the complete normalized input, configuration,
    versions, corpus digests, and every result/leakage manifest.
    """
    config_manifest = cfg.manifest()
    return {
        "schema_version": BACKTEST_MANIFEST_SCHEMA,
        "snapshot_id": snapshot.snapshot_id,
        "input_manifest_hash": snapshot.input_manifest_hash(),
        "config_manifest_hash": _sha256_reference(config_manifest),
        "config_manifest": config_manifest,
        "versions": {
            "engine_version": full_run.engine_version,
            "feature_version": full_run.feature_version,
            "taxonomy_version": full_run.taxonomy_version,
        },
        "corpus_lineage_refs": corpus_lineage_references(snapshot),
        "cutoffs": list(cutoffs),
        "cutoff_runs": [_run_reference(run) for run in cutoff_runs],
        "full_run": _run_reference(full_run),
    }


def backtest_manifest_sha256(manifest: dict) -> str:
    """Return the full canonical digest for a backtest audit manifest."""
    return _sha256_reference(manifest)


def backtest_identity(manifest: dict) -> str:
    """Return the compact deterministic id an API can use for a backtest."""
    digest = backtest_manifest_sha256(manifest).removeprefix("sha256:")
    return f"bt_{digest[:16]}"


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def run_backtest(snapshot, taxonomy, cutoffs, cfg: EngineConfig = DEFAULT_CONFIG) -> dict:
    cutoffs = sorted(cutoffs)
    per_cutoff = []
    cutoff_runs = []
    for c in cutoffs:
        run = run_pipeline(snapshot, taxonomy, cfg, cutoff_date=c)
        cutoff_runs.append(run)
        # hard leakage check for every historical run, on both dates
        cut = leakage.apply_cutoff(snapshot.observations, snapshot.sources, c)
        leakage.assert_no_leakage(cut["observations"], cut["sources"], c)
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
    manifest = build_backtest_manifest(snapshot, cfg, cutoffs, cutoff_runs, full)
    return {
        "cutoffs": cutoffs,
        "tracks": tracks,
        "median_early_discovery_lead_days": median_lead,
        "false_positive_candidates": false_positives,
        "future_leakage_violations": 0,  # would have raised above otherwise
        "backtest_identity": backtest_identity(manifest),
        "backtest_manifest_hash": backtest_manifest_sha256(manifest),
        "backtest_manifest": manifest,
    }

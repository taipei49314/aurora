"""Run comparison + first-divergence analysis (spec §21).

Comparing two Research Runs must not merely report "scores differ" — it must
identify the FIRST explainable stage at which the runs began to diverge and what
changed. We walk stages in pipeline order (inputs -> clustering -> scoring ->
classification) and stop at the first that differs.
"""
from __future__ import annotations


def _cluster_signatures(run):
    return {h.hypothesis_id: set(h.entity_ids) for h in run.hypotheses}


def compare(run_a, run_b) -> dict:
    a_by_ent = {frozenset(h.entity_ids): h for h in run_a.hypotheses}
    b_by_ent = {frozenset(h.entity_ids): h for h in run_b.hypotheses}
    status_changes, score_changes = [], []
    for key, ha in a_by_ent.items():
        hb = b_by_ent.get(key)
        if hb is None:
            continue
        if ha.status != hb.status:
            status_changes.append({"entities": sorted(key), "before": ha.status, "after": hb.status})
        if abs(ha.overall_score - hb.overall_score) > 1e-6:
            score_changes.append({"entities": sorted(key), "before": ha.overall_score, "after": hb.overall_score})
    added = [sorted(k) for k in b_by_ent if k not in a_by_ent]
    removed = [sorted(k) for k in a_by_ent if k not in b_by_ent]
    return {
        "status_changes": status_changes,
        "score_changes": score_changes,
        "clusters_added": added,
        "clusters_removed": removed,
    }


def first_divergence(run_a, run_b) -> dict:
    """Return the first pipeline stage where the two runs differ, with details."""
    # stage: inputs
    if run_a.input_manifest_hash != run_b.input_manifest_hash:
        return {"first_divergence_stage": "inputs",
                "changed_input": "snapshot/observation set differs",
                "before": run_a.input_manifest_hash, "after": run_b.input_manifest_hash,
                "affected_entities": [], "affected_hypotheses": []}
    # stage: cutoff / temporal
    if run_a.cutoff_date != run_b.cutoff_date:
        return {"first_divergence_stage": "cutoff",
                "changed_input": "cutoff_date",
                "before": run_a.cutoff_date, "after": run_b.cutoff_date,
                "affected_entities": [], "affected_hypotheses": []}
    # stage: config (clustering / scoring / taxonomy)
    if run_a.algorithm_config != run_b.algorithm_config:
        return {"first_divergence_stage": "clustering_config", "changed_input": "algorithm_config",
                "before": run_a.algorithm_config, "after": run_b.algorithm_config,
                "affected_entities": [], "affected_hypotheses": []}
    if run_a.scoring_config != run_b.scoring_config:
        return {"first_divergence_stage": "scoring_config", "changed_input": "scoring_config",
                "before": run_a.scoring_config, "after": run_b.scoring_config,
                "affected_entities": [], "affected_hypotheses": []}
    if run_a.taxonomy_version != run_b.taxonomy_version:
        return {"first_divergence_stage": "taxonomy_version", "changed_input": "taxonomy_version",
                "before": run_a.taxonomy_version, "after": run_b.taxonomy_version,
                "affected_entities": [], "affected_hypotheses": []}
    # stage: cluster membership
    sig_a, sig_b = _cluster_signatures(run_a), _cluster_signatures(run_b)
    if set(map(frozenset, sig_a.values())) != set(map(frozenset, sig_b.values())):
        return {"first_divergence_stage": "cluster_membership",
                "changed_input": "cluster formation changed",
                "before": [sorted(s) for s in sig_a.values()],
                "after": [sorted(s) for s in sig_b.values()],
                "affected_entities": [], "affected_hypotheses": []}
    # stage: scoring / classification
    diff = compare(run_a, run_b)
    if diff["status_changes"] or diff["score_changes"]:
        first = (diff["status_changes"] or diff["score_changes"])[0]
        return {"first_divergence_stage": "scoring_or_classification",
                "changed_input": "scores/status changed with identical inputs & config",
                "before": first.get("before"), "after": first.get("after"),
                "affected_entities": first["entities"],
                "affected_hypotheses": [],
                "detail": diff}
    return {"first_divergence_stage": None, "changed_input": None,
            "before": None, "after": None, "affected_entities": [], "affected_hypotheses": []}

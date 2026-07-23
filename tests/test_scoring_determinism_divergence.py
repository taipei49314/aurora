"""Scoring transparency, determinism, taxonomy, and first-divergence."""
from __future__ import annotations

import pytest as _pytest
pytestmark = _pytest.mark.unit

from aurora import run_pipeline, DEFAULT_CONFIG, EngineConfig
from aurora.config import ScoringConfig
from aurora.scoring import assemble, saturating
from aurora import divergence


def test_scoring_is_explicit_linear_combination():
    cfg = ScoringConfig()
    comps = {k: 50.0 for k in cfg.weights}
    comps.update({"hype_risk_score": 0, "contradiction_score": 0, "data_quality_penalty": 0})
    out = assemble(comps, cfg)
    # all component scores 50, weights sum to 1 -> weighted sum 50
    assert abs(out["weighted_sum"] - 50.0) < 1e-6
    assert abs(out["overall_score"] - 50.0) < 1e-6


def test_scoring_contributions_sum_to_weighted_sum():
    cfg = ScoringConfig()
    comps = {k: (i * 7) % 100 for i, k in enumerate(cfg.weights)}
    comps.update({"hype_risk_score": 0, "contradiction_score": 0, "data_quality_penalty": 0})
    out = assemble(comps, cfg)
    total = sum(c["contribution"] for c in out["contributions"].values())
    assert abs(total - out["weighted_sum"]) < 0.05


def test_hype_penalty_reduces_overall():
    cfg = ScoringConfig()
    base = {k: 60.0 for k in cfg.weights}
    base.update({"hype_risk_score": 0, "contradiction_score": 0, "data_quality_penalty": 0})
    hyped = dict(base, hype_risk_score=90)
    assert assemble(hyped, cfg)["overall_score"] < assemble(base, cfg)["overall_score"]


def test_saturating_bounds():
    assert saturating(0, 0.3) == 0.0
    assert saturating(0.3, 0.3) == 100.0
    assert saturating(1.0, 0.3) == 100.0


def test_determinism_50_runs(fast_snapshot, taxonomy):
    ref = run_pipeline(fast_snapshot, taxonomy, DEFAULT_CONFIG)
    ref_sig = [(h.hypothesis_id, h.status, h.overall_score, tuple(h.entity_ids)) for h in ref.hypotheses]
    for _ in range(49):
        r = run_pipeline(fast_snapshot, taxonomy, DEFAULT_CONFIG)
        sig = [(h.hypothesis_id, h.status, h.overall_score, tuple(h.entity_ids)) for h in r.hypotheses]
        assert sig == ref_sig
        assert r.result_manifest_hash == ref.result_manifest_hash


def test_determinism_full_scale_smoke(snapshot, taxonomy):
    """Determinism also holds at full corpus scale (fewer repeats for speed)."""
    a = run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG)
    b = run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG)
    assert a.result_manifest_hash == b.result_manifest_hash


def test_divergence_on_cutoff_change(snapshot, taxonomy):
    a = run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG, cutoff_date="2020-12-31")
    b = run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG, cutoff_date=None)
    d = divergence.first_divergence(a, b)
    assert d["first_divergence_stage"] in {"inputs", "cutoff"}


def test_divergence_on_scoring_weight_change(snapshot, taxonomy):
    a = run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG)
    cfg2 = EngineConfig(scoring=ScoringConfig(version="0.1.1",
                                              weights=dict(DEFAULT_CONFIG.scoring.weights, novelty_score=0.30)))
    # renormalize not required for the test; just ensure divergence is explained
    b = run_pipeline(snapshot, taxonomy, cfg2)
    d = divergence.first_divergence(a, b)
    assert d["first_divergence_stage"] in {"scoring_config", "scoring_or_classification"}
    assert d["first_divergence_stage"] is not None


def test_identical_runs_have_no_divergence(snapshot, taxonomy):
    a = run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG)
    b = run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG)
    d = divergence.first_divergence(a, b)
    assert d["first_divergence_stage"] is None

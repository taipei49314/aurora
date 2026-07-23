"""Hype filter, counterevidence downgrade, bottleneck ranking units."""
from __future__ import annotations

import pytest as _pytest
pytestmark = _pytest.mark.unit

from aurora.hype import hype_assessment
from aurora.counterevidence import analyze
from conftest import hyp_for


def test_hype_factors_sum_to_score(run, name_to_entity):
    h = hyp_for(run, ["MetaMart", "AvatarAisle"], name_to_entity)
    hy = h.score_explanation["hype"]
    recomputed = 100.0 * sum(hy["weights"][k] * v for k, v in hy["factors"].items())
    assert abs(recomputed - hy["hype_risk_score"]) < 0.5


def test_hype_penalizes_low_real_investment(run, name_to_entity):
    hype = hyp_for(run, ["MetaMart", "AvatarAisle"], name_to_entity)
    real = hyp_for(run, ["FerroGrid Power", "LongHaul Energy"], name_to_entity)
    assert hype.hype_risk_score > real.hype_risk_score
    assert hype.real_investment_score < real.real_investment_score


def test_hype_low_independence_ratio(run, name_to_entity):
    h = hyp_for(run, ["MetaMart", "AvatarAisle"], name_to_entity)
    assert h.score_explanation["hype"]["independence_ratio"] < 0.6


def test_counterevidence_downgrades_overall(run, name_to_entity):
    failed = hyp_for(run, ["AlgaJet", "GreenLipid Fuels"], name_to_entity)
    scoring = failed.score_explanation["scoring"]
    # the contradiction penalty must be actively subtracting
    assert scoring["penalties"]["contradiction"] > 0
    assert failed.overall_score < scoring["weighted_sum"]


def test_missing_evidence_reported(run, name_to_entity):
    h = hyp_for(run, ["QubitChain", "EntangleLedger"], name_to_entity)
    # a hype cluster is missing hiring/capex/supplier evidence
    assert "SUPPLIER_RELATIONSHIP" in h.missing_evidence or "CAPEX_ACTIVITY" in h.missing_evidence


def test_bottleneck_ranking_is_structural_not_volume(run, name_to_entity):
    h = hyp_for(run, ["FerroGrid Power", "LongHaul Energy"], name_to_entity)
    bns = h.score_explanation["bottlenecks"]
    supplier = next(b for b in bns if b["entity_id"] == name_to_entity["FerroPore Labs"])
    assert supplier["centrality"] >= 0.9
    assert supplier["downstream_dependents"]

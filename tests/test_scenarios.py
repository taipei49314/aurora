"""End-to-end acceptance scenarios A-H (spec §24)."""
from __future__ import annotations

import pytest
pytestmark = pytest.mark.e2e

from conftest import hyp_for


@pytest.mark.parametrize("names,expected", [
    (["FerroGrid Power", "LongHaul Energy", "OxaCell Systems"], {"INDUSTRY_CANDIDATE", "EMERGING_CAPABILITY_CLUSTER"}),
    (["MycoStructural", "FungiForm Materials"], {"INDUSTRY_CANDIDATE", "EMERGING_CAPABILITY_CLUSTER"}),
    (["SpikeEdge", "MemSense", "NeuroPixel"], {"INDUSTRY_CANDIDATE", "EMERGING_CAPABILITY_CLUSTER"}),
])
def test_scenario_a_dispersed_signals_form_industry(run, name_to_entity, names, expected):
    h = hyp_for(run, names, name_to_entity)
    assert h.status in expected
    # evidence chain must be present
    assert h.strongest_supporting_evidence
    assert h.observation_ids


@pytest.mark.parametrize("names", [
    ["MetaMart", "AvatarAisle", "ImmersaShop"],
    ["QubitChain", "EntangleLedger", "QuantumMint"],
])
def test_scenario_b_hype_is_flagged_not_top(run, name_to_entity, names):
    h = hyp_for(run, names, name_to_entity)
    assert h.status == "HYPE_CLUSTER"
    assert h.hype_risk_score >= 60
    # hype must never outrank a real candidate
    candidates = [x for x in run.hypotheses if x.status == "INDUSTRY_CANDIDATE"]
    assert all(h.overall_score < c.overall_score for c in candidates)


def test_scenario_b_quantum_buzzword_not_inflated(run, name_to_entity):
    q = hyp_for(run, ["QubitChain", "EntangleLedger"], name_to_entity)
    # despite "quantum"/"blockchain" buzzwords, score stays low
    assert q.overall_score < 40


@pytest.mark.parametrize("names", [
    ["SynergyCloud Fabric", "NextGen Colo", "HyperRack Systems"],
    ["MobilityForge", "NextAxle Systems", "DriveCore Solutions"],
])
def test_scenario_c_renamed_mature_industry(run, name_to_entity, names):
    h = hyp_for(run, names, name_to_entity)
    assert h.status == "EXISTING_INDUSTRY_VARIANT"
    assert h.existing_industry_similarity["similarity"] >= 0.5


def test_scenario_d_small_supplier_is_top_bottleneck(run, name_to_entity):
    h = hyp_for(run, ["FerroGrid Power", "LongHaul Energy"], name_to_entity)
    bns = h.score_explanation["bottlenecks"]
    top = bns[0]
    assert top["entity_id"] == name_to_entity["FerroPore Labs"]
    # ranked above the large, news-heavy integrators
    integrator_scores = [b["bottleneck_score"] for b in bns
                         if b["entity_id"] == name_to_entity["MegaHour Grid"]]
    assert not integrator_scores or top["bottleneck_score"] > max(integrator_scores)


def test_scenario_e_single_giant_insufficient(run, name_to_entity):
    h = hyp_for(run, ["Monolith Corp"], name_to_entity)
    assert h.status == "INSUFFICIENT_EVIDENCE"


def test_scenario_f_failed_cluster_downgraded(run, name_to_entity):
    h = hyp_for(run, ["AlgaJet", "GreenLipid Fuels"], name_to_entity)
    assert h.status in {"REJECTED", "DORMANT"}
    assert h.contradiction_score >= 45
    assert h.strongest_counterevidence
    assert h.disconfirmation_conditions


def test_scenario_h_naming_gap_high_for_latent_low_for_mature(run, name_to_entity):
    latent = hyp_for(run, ["FerroGrid Power", "LongHaul Energy"], name_to_entity)
    mature = hyp_for(run, ["SynergyCloud Fabric", "NextGen Colo"], name_to_entity)
    assert latent.naming_gap_score > mature.naming_gap_score


def test_every_hypothesis_has_provenance(run):
    for h in run.hypotheses:
        assert h.observation_ids, f"{h.generated_name} lacks provenance"
        assert h.score_explanation.get("scoring")
        assert h.disconfirmation_conditions


def test_scenario_d_shared_supplier_has_no_false_substitutes(run, name_to_entity):
    """Regression (self-audit known issue): the co-listed component entity used
    to be mis-counted as an alternative supplier, giving substitutability 0.5.
    An alternative must serve the same downstream via the same dependency type."""
    h = hyp_for(run, ["FerroGrid Power", "LongHaul Energy"], name_to_entity)
    top = h.score_explanation["bottlenecks"][0]
    assert top["entity_id"] == name_to_entity["FerroPore Labs"]
    assert top["substitutability"] == 0.0
    assert top["substitute_exists"] is False
    assert top["supplier_concentration"] == 1.0

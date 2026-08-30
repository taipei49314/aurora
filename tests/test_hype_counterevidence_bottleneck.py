"""Hype filter, counterevidence downgrade, bottleneck ranking units."""
from __future__ import annotations

import pytest as _pytest
pytestmark = _pytest.mark.unit

from aurora.hype import hype_assessment
from aurora.counterevidence import analyze
from aurora.bottleneck import analyze as analyze_bottlenecks
from aurora.models import Entity, Observation, Source
from aurora.pipeline import run_pipeline
from aurora.signals import entity_signal_summary
from aurora.store import make_snapshot
from aurora.value_chain import build as build_value_chain
from aurora import DEFAULT_CONFIG
from conftest import hyp_for


def _observation(
    observation_id,
    observation_type,
    *,
    value=None,
    subject="upstream",
    object_entity=None,
):
    return Observation(
        observation_id=observation_id,
        source_id=f"source-{observation_id}",
        observed_at="2026-01-01",
        observation_type=observation_type,
        subject_entity=subject,
        object_entity=object_entity,
        numeric_value=value,
        unit=None,
        text_excerpt=observation_id,
        confidence=1.0,
    )


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


def test_bottleneck_scarcity_provenance_excludes_positive_expansion():
    upstream = Entity("upstream", "COMPONENT", "Upstream")
    downstream = Entity("downstream", "COMPANY", "Downstream")

    observations = [
        _observation(
            "dependency",
            "TECHNICAL_DEPENDENCY",
            subject="downstream",
            object_entity="upstream",
        ),
        _observation("positive-capacity", "CAPACITY_EXPANSION", value=10),
        _observation("negative-capacity", "CAPACITY_EXPANSION", value=-1),
        _observation("lead-time", "LEAD_TIME_PRESSURE", value=12),
    ]
    result = analyze_bottlenecks(
        "hypothesis",
        ["upstream", "downstream"],
        [upstream, downstream],
        observations,
        [["upstream", "downstream"]],
        {"upstream": {"downstream": 1.0}, "downstream": {"upstream": 1.0}},
    )
    candidate = next(c for c in result["candidates"] if c.entity_id == "upstream")
    assert candidate.scarcity_evidence_ids == ["negative-capacity", "lead-time"]


def test_negative_capacity_is_counterevidence_not_real_investment():
    positive = _observation("positive-capacity", "CAPACITY_EXPANSION", value=10)
    negative = _observation("negative-capacity", "CAPACITY_EXPANSION", value=-1)

    counter = analyze(["upstream"], [positive, negative], {})
    assert counter["strongest_supporting_evidence"] == ["positive-capacity"]
    assert counter["strongest_counterevidence"] == ["negative-capacity"]

    hype = hype_assessment(["upstream"], [positive, negative])
    assert hype["real_investment_ratio"] == 0.5
    negative_only = hype_assessment(["upstream"], [negative])
    assert negative_only["real_investment_ratio"] == 0.0
    assert negative_only["factors"]["no_supply_chain"] == 1.0

    signal = entity_signal_summary([positive, negative], {})["upstream"]
    assert signal["real_investment_count"] == 1
    assert signal["negative_count"] == 1


def test_capacity_role_promotion_preserves_value_chain_coverage():
    company = Entity("upstream", "COMPANY", "Upstream")
    baseline = build_value_chain("hypothesis", ["upstream"], [company], [])
    negative = build_value_chain(
        "hypothesis",
        ["upstream"],
        [company],
        [_observation("negative-capacity", "CAPACITY_EXPANSION", value=-1)],
    )

    assert baseline["nodes"][0].role == "INTEGRATION"
    for value in (None, 0, 10):
        positive = build_value_chain(
            "hypothesis",
            ["upstream"],
            [company],
            [_observation("positive-capacity", "CAPACITY_EXPANSION", value=value)],
        )
        assert positive["nodes"][0].role == "INFRASTRUCTURE"
        assert positive["value_chain_score"] == baseline["value_chain_score"]
    assert negative["nodes"][0].role == "INTEGRATION"
    assert negative["value_chain_score"] == baseline["value_chain_score"]


def test_pipeline_capacity_sign_controls_real_investment_score(taxonomy):
    entities = [
        Entity(
            f"company-{index}",
            "COMPANY",
            f"Company {index}",
            description="shared precision lattice manufacturing platform",
        )
        for index in range(3)
    ]

    def score_for(value):
        sources = []
        observations = []
        for index, entity in enumerate(entities):
            source_id = f"source-{index}"
            sources.append(Source(
                source_id=source_id,
                source_type="COMPANY_FILING",
                publisher=entity.canonical_name,
                title=f"Capacity filing {index}",
                published_at="2026-01-01",
                retrieved_at="2026-01-02",
                url_or_local_path=f"local://capacity-{index}",
                content_hash=f"content-{index}",
                independence_group=source_id,
                reliability_tier="A",
                language="en",
            ))
            observation = _observation(
                f"capacity-{index}",
                "CAPACITY_EXPANSION",
                value=value,
                subject=entity.entity_id,
            )
            observation.source_id = source_id
            observation.metadata["source_type"] = "COMPANY_FILING"
            observations.append(observation)
        snapshot = make_snapshot(
            entities,
            sources,
            observations,
            {source.source_id: source.source_id for source in sources},
            [],
            "2026-01-02T00:00:00+00:00",
        )
        run = run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG)
        assert len(run.hypotheses) == 1
        return run.hypotheses[0].real_investment_score

    assert score_for(-1) == 0.0
    assert score_for(None) == score_for(0) == score_for(1) == 100.0

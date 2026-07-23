"""data_quality_penalty incorporates reliability_tier (engine 0.1.1)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from aurora.pipeline import (
    _data_quality_assessment,
    _data_quality_penalty,
    _obs_reliability_tier,
)


def _obs(*, date="2020-01-01", conf=0.8, tier=None, source_id="s1"):
    meta = {}
    if tier is not None:
        meta["reliability_tier"] = tier
    return SimpleNamespace(
        observed_at=date,
        confidence=conf,
        source_id=source_id,
        metadata=meta,
    )


@pytest.mark.unit
def test_all_A_tiers_cheaper_than_all_D():
    a = [_obs(tier="A") for _ in range(4)]
    d = [_obs(tier="D") for _ in range(4)]
    pen_a = _data_quality_penalty(a)
    pen_d = _data_quality_penalty(d)
    assert pen_a < pen_d
    # pure date/conf clean: only reliability contributes (0 vs 15)
    assert pen_a == 0.0
    assert pen_d == 15.0


@pytest.mark.unit
def test_missing_dates_still_penalize():
    undated = [_obs(date=None, tier="A") for _ in range(4)]
    pen = _data_quality_penalty(undated)
    # missing fraction 1.0 on half of the 2-factor term → 12.5, reliability 0
    assert pen == 12.5


@pytest.mark.unit
def test_tier_from_source_map_when_metadata_absent():
    obs = [_obs(tier=None, source_id="x")]
    sources = {"x": SimpleNamespace(reliability_tier="D")}
    assert _obs_reliability_tier(obs[0], sources) == "D"
    assert _data_quality_penalty(obs, sources) == 15.0


@pytest.mark.unit
def test_metadata_tier_overrides_source():
    obs = [_obs(tier="A", source_id="x")]
    sources = {"x": SimpleNamespace(reliability_tier="D")}
    assert _obs_reliability_tier(obs[0], sources) == "A"
    assert _data_quality_penalty(obs, sources) == 0.0


@pytest.mark.unit
def test_assessment_breakdown_matches_penalty():
    mixed = [_obs(tier="A"), _obs(tier="D"), _obs(date=None, tier="C")]
    assess = _data_quality_assessment(mixed)
    assert assess["data_quality_penalty"] == _data_quality_penalty(mixed)
    assert "tier_counts" in assess["factors"]
    assert assess["factors"]["tier_counts"]["D"] == 1
    assert assess["factors"]["reliability_penalty"] > 0
    assert assess["factors"]["date_conf_penalty"] > 0


@pytest.mark.integration
def test_import_stamps_reliability_on_observations():
    from aurora import import_package

    pkg = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [{
            "ref": "s1",
            "source_type": "PATENT",
            "publisher": "USPTO",
            "title": "T",
            "excerpt": "E",
            "reliability_tier": "A",
            "published_at": "2020-01-01",
        }],
        "observations": [{
            "source_ref": "s1",
            "observation_type": "PATENT_ACTIVITY",
            "subject": "Acme",
            "observed_at": "2020-01-01",
            "text_excerpt": "patent text",
            "confidence": 0.9,
        }],
    }
    snap = import_package(pkg)
    assert snap.import_errors == []
    assert snap.observations[0].metadata.get("reliability_tier") == "A"

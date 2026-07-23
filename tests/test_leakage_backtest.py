"""Temporal cutoff, future-leakage prevention, historical backtest."""
from __future__ import annotations

import pytest as _pytest
pytestmark = _pytest.mark.integration

import pytest

from aurora import run_pipeline, DEFAULT_CONFIG
from aurora import leakage
from aurora.backtest import run_backtest
from aurora.errors import AuroraError


def test_cutoff_excludes_future_observations(snapshot):
    cut = leakage.apply_cutoff(snapshot.observations, snapshot.sources, "2021-12-31")
    assert cut["manifest"]["excluded_future_observation_count"] > 0
    for o in cut["observations"]:
        assert o.observed_at is None or o.observed_at <= "2021-12-31"


def test_no_leakage_assertion_passes_on_clean_subset(snapshot):
    cut = leakage.apply_cutoff(snapshot.observations, snapshot.sources, "2022-06-30")
    leakage.assert_no_leakage(cut["observations"], "2022-06-30")  # must not raise


def test_leakage_detected_when_future_slips_in(snapshot):
    future = [o for o in snapshot.observations if o.observed_at and o.observed_at > "2021-12-31"][:1]
    with pytest.raises(AuroraError) as exc:
        leakage.assert_no_leakage(future, "2021-12-31")
    assert exc.value.error_code == "FUTURE_DATA_LEAKAGE"


def test_invalid_cutoff_raises():
    with pytest.raises(AuroraError) as exc:
        leakage.parse_cutoff("not-a-date")
    assert exc.value.error_code == "INVALID_CUTOFF_DATE"


def test_cutoff_run_has_fewer_or_equal_candidates(snapshot, taxonomy):
    early = run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG, cutoff_date="2021-12-31")
    full = run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG, cutoff_date=None)
    n_early = sum(1 for h in early.hypotheses if h.status == "INDUSTRY_CANDIDATE")
    n_full = sum(1 for h in full.hypotheses if h.status == "INDUSTRY_CANDIDATE")
    assert n_early <= n_full


def test_backtest_reports_no_leakage_and_tracks(snapshot, taxonomy):
    bt = run_backtest(snapshot, taxonomy, ["2020-12-31", "2022-12-31", "2024-12-31"], DEFAULT_CONFIG)
    assert bt["future_leakage_violations"] == 0
    assert bt["tracks"]
    # hype/failed clusters must not be reported as early industry candidates
    assert bt["false_positive_candidates"] == [] or all(
        "quantum" not in n and "metaverse" not in n for n in bt["false_positive_candidates"])


def test_backtest_detects_industries_before_full_run(snapshot, taxonomy):
    bt = run_backtest(snapshot, taxonomy, ["2021-12-31", "2023-12-31", "2025-06-30"], DEFAULT_CONFIG)
    emerging_tracks = [t for t in bt["tracks"]
                       if t["final_status"] == "INDUSTRY_CANDIDATE" and t["first_emerging_cutoff"]]
    assert emerging_tracks, "at least one real industry should be detectable before the last cutoff"

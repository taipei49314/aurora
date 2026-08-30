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
    leakage.assert_no_leakage(cut["observations"], cut["sources"], "2022-06-30")  # must not raise


def test_leakage_detected_when_future_slips_in(snapshot):
    future = [o for o in snapshot.observations if o.observed_at and o.observed_at > "2021-12-31"][:1]
    with pytest.raises(AuroraError) as exc:
        leakage.assert_no_leakage(future, snapshot.sources, "2021-12-31")
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


def test_pipeline_anchors_hype_windows_at_cutoff(snapshot, taxonomy, monkeypatch):
    import aurora.pipeline as pipeline_module

    real_assessment = pipeline_module.hype_assessment
    seen_as_of = []

    def capture_assessment(cluster, observations, *, as_of=None):
        seen_as_of.append(as_of)
        return real_assessment(cluster, observations, as_of=as_of)

    monkeypatch.setattr(pipeline_module, "hype_assessment", capture_assessment)
    run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG, cutoff_date="2021-12-31")

    assert seen_as_of
    assert set(seen_as_of) == {"2021-12-31"}


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


# --- source publication date (spec §19: available at the cutoff, not merely old) ---

def _src(source_id, published_at):
    from aurora.models import Source
    return Source(source_id=source_id, source_type="news", publisher="P",
                  title="t", published_at=published_at, retrieved_at="2024-01-01",
                  url_or_local_path="x", content_hash="h", independence_group="g",
                  reliability_tier="B", language="en")


def _obs(observation_id, source_id, observed_at):
    from aurora.models import Observation
    return Observation(observation_id=observation_id, source_id=source_id,
                       observed_at=observed_at, observation_type="hiring",
                       subject_entity="e1", object_entity=None, numeric_value=None,
                       unit=None, text_excerpt="t", confidence=0.9)


def test_retrospective_source_is_excluded():
    """A 2023 article about a 2020 event was not readable at a 2021 cutoff."""
    cut = leakage.apply_cutoff([_obs("o1", "s_late", "2020-05-01")],
                               [_src("s_late", "2023-06-01")], "2021-12-31")
    assert cut["observations"] == [], "a document published after the cutoff leaked in"
    assert cut["manifest"]["excluded_future_source_observation_count"] == 1
    assert cut["manifest"]["excluded_future_observation_count"] == 0, \
        "the observation itself is old; it is the document that is from the future"


def test_undated_source_is_excluded():
    """Not knowing when something became public is not evidence that it was."""
    cut = leakage.apply_cutoff([_obs("o1", "s_undated", "2020-05-01")],
                               [_src("s_undated", None)], "2021-12-31")
    assert cut["observations"] == []
    assert cut["manifest"]["excluded_undated_source_observation_count"] == 1


def test_observation_whose_source_is_missing_is_excluded():
    cut = leakage.apply_cutoff([_obs("o1", "s_absent", "2020-05-01")], [], "2021-12-31")
    assert cut["observations"] == []
    assert cut["manifest"]["excluded_undated_source_observation_count"] == 1


def test_source_published_on_the_cutoff_is_kept():
    """The boundary is inclusive on both dates; the fix must not over-reject."""
    cut = leakage.apply_cutoff([_obs("o1", "s_edge", "2020-05-01")],
                               [_src("s_edge", "2021-12-31")], "2021-12-31")
    assert [o.observation_id for o in cut["observations"]] == ["o1"]
    assert cut["manifest"]["included_observation_count"] == 1


def test_assert_no_leakage_catches_a_retrospective_source():
    """The hard re-check must see the source date, not only the event date."""
    obs = [_obs("o1", "s_late", "2020-05-01")]
    with pytest.raises(AuroraError) as exc:
        leakage.assert_no_leakage(obs, [_src("s_late", "2023-06-01")], "2021-12-31")
    assert exc.value.error_code == "FUTURE_DATA_LEAKAGE"
    assert exc.value.details["source_published_at"] == "2023-06-01"


def test_assert_no_leakage_requires_sources():
    """Calling it without sources must be impossible, not silently half-checked."""
    with pytest.raises(TypeError):
        leakage.assert_no_leakage([_obs("o1", "s", "2020-01-01")], "2021-12-31")

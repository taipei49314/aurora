"""Calendar-window semantics for the hype temporal fade factor."""
from __future__ import annotations

import pytest

from aurora.hype import hype_assessment
from aurora.models import Observation


pytestmark = pytest.mark.unit


def _observation(index, observed_at):
    return Observation(
        observation_id=f"observation-{index}",
        source_id=f"source-{index}",
        observed_at=observed_at,
        observation_type="PRODUCT_LAUNCH",
        subject_entity="cluster-member",
        object_entity=None,
        numeric_value=None,
        unit=None,
        text_excerpt=f"observation {index}",
        confidence=1.0,
    )


def _assessment(dates, *, as_of):
    observations = [_observation(index, observed_at) for index, observed_at in enumerate(dates)]
    return hype_assessment(["cluster-member"], observations, as_of=as_of)


def test_dense_early_activity_followed_by_silence_is_faded():
    result = _assessment(
        [f"2026-01-{day:02d}" for day in range(1, 7)],
        as_of="2026-09-30",
    )

    assert result["factors"]["faded"] == 1.0
    assert result["fade_analysis"]["window_counts"] == {
        "early": 6,
        "middle": 0,
        "recent": 0,
    }


def test_uniform_calendar_activity_is_not_faded():
    result = _assessment(
        [
            "2026-01-15", "2026-02-15",
            "2026-04-15", "2026-05-15",
            "2026-07-15", "2026-08-15",
        ],
        as_of="2026-09-30",
    )

    assert result["fade_analysis"]["window_counts"] == {
        "early": 2,
        "middle": 2,
        "recent": 2,
    }
    assert result["factors"]["faded"] == 0.0


def test_rising_recent_activity_is_not_faded():
    result = _assessment(
        [
            "2026-01-15",
            "2026-04-15", "2026-05-15",
            "2026-07-15", "2026-08-15", "2026-09-15",
        ],
        as_of="2026-09-30",
    )

    assert result["fade_analysis"]["window_counts"] == {
        "early": 1,
        "middle": 2,
        "recent": 3,
    }
    assert result["factors"]["faded"] == 0.0


def test_fewer_than_six_dated_observations_do_not_score_fade():
    result = _assessment(
        [f"2026-01-{day:02d}" for day in range(1, 6)],
        as_of="2026-09-30",
    )

    assert result["factors"]["faded"] == 0.0
    assert result["fade_analysis"]["dated_observation_count"] == 5
    assert result["fade_analysis"]["minimum_dated_observations"] == 6
    assert result["fade_analysis"]["window_days"] is None


def test_undated_observations_neither_meet_threshold_nor_create_fade():
    dates = [f"2026-01-{day:02d}" for day in range(1, 6)] + [None] * 10
    result = _assessment(dates, as_of="2026-09-30")

    assert result["factors"]["faded"] == 0.0
    assert result["fade_analysis"]["dated_observation_count"] == 5
    assert result["fade_analysis"]["undated_observation_count"] == 10


def test_as_of_cutoff_defines_the_recent_window():
    dates = [f"2026-01-{day:02d}" for day in range(1, 7)]

    at_activity = _assessment(dates, as_of="2026-01-06")
    after_silence = _assessment(dates, as_of="2026-09-30")

    assert at_activity["factors"]["faded"] == 0.0
    assert at_activity["fade_analysis"]["window_counts"]["recent"] == 2
    assert after_silence["factors"]["faded"] == 1.0
    assert after_silence["fade_analysis"]["window_counts"]["recent"] == 0
    assert after_silence["fade_analysis"]["as_of"] == "2026-09-30"


def test_observations_after_as_of_do_not_enter_fade_windows():
    dates = [f"2026-01-{day:02d}" for day in range(1, 7)] + ["2027-01-01"] * 6
    result = _assessment(dates, as_of="2026-09-30")

    assert result["factors"]["faded"] == 1.0
    assert result["fade_analysis"]["dated_observation_count"] == 6
    assert result["fade_analysis"]["excluded_after_as_of_count"] == 6

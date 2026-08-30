"""Lead-time unit and boundary contracts for bottleneck scoring."""
from __future__ import annotations

import pytest

from aurora.bottleneck import analyze
from aurora.models import Entity, Observation

pytestmark = pytest.mark.unit


def _observation(observation_id, observation_type, *, value=None, unit=None):
    return Observation(
        observation_id=observation_id,
        source_id=f"source-{observation_id}",
        observed_at="2026-01-01",
        observation_type=observation_type,
        subject_entity="upstream" if observation_type == "LEAD_TIME_PRESSURE" else "downstream",
        object_entity="upstream" if observation_type == "TECHNICAL_DEPENDENCY" else None,
        numeric_value=value,
        unit=unit,
        text_excerpt=observation_id,
        confidence=1.0,
    )


def _candidate(*pressures):
    entities = [
        Entity("upstream", "COMPONENT", "Upstream"),
        Entity("downstream", "COMPANY", "Downstream"),
    ]
    observations = [
        _observation("dependency", "TECHNICAL_DEPENDENCY"),
        *pressures,
    ]
    result = analyze(
        "hypothesis",
        ["upstream", "downstream"],
        entities,
        observations,
        [["upstream", "downstream"]],
        {"upstream": {"downstream": 1.0}, "downstream": {"upstream": 1.0}},
    )
    return next(candidate for candidate in result["candidates"] if candidate.entity_id == "upstream")


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (None, "months", 0.0),
        (0, "months", 0.0),
        (-12, "months", 0.0),
        (12, None, 0.0),
        (float("nan"), "months", 0.0),
        (float("inf"), "months", 0.0),
        pytest.param(10**10_000, "months", 0.0, id="overflowing-integer"),
        (365, "days", 0.5),
        (52, "weeks", 0.5),
        (12, "months", 0.5),
        (12, "fortnights", 0.0),
        (24, "months", 1.0),
        (48, "months", 1.0),
    ],
)
def test_lead_time_normalization_table(value, unit, expected):
    candidate = _candidate(_observation("pressure", "LEAD_TIME_PRESSURE", value=value, unit=unit))
    assert candidate.lead_time == expected
    assert candidate.scarcity_evidence_ids == ([] if expected == 0.0 else ["pressure"])


@pytest.mark.parametrize(
    ("unit", "horizon"),
    [
        ("DAY", 730),
        ("days", 730),
        ("WEEK", 104),
        ("WeEkS", 104),
        ("MONTH", 24),
        ("MONTHS", 24),
        ("d", 730),
        ("wk", 104),
        ("mos", 24),
    ],
)
def test_lead_time_accepts_case_plural_and_common_abbreviations(unit, horizon):
    candidate = _candidate(_observation("pressure", "LEAD_TIME_PRESSURE", value=horizon, unit=unit))
    assert candidate.lead_time == 1.0


def test_multiple_lead_time_observations_take_maximum():
    candidate = _candidate(
        _observation("months", "LEAD_TIME_PRESSURE", value=6, unit="months"),
        _observation("days", "LEAD_TIME_PRESSURE", value=270, unit="days"),
        _observation("weeks", "LEAD_TIME_PRESSURE", value=52, unit="weeks"),
        _observation("unknown", "LEAD_TIME_PRESSURE", value=10_000, unit="fortnights"),
    )
    assert candidate.lead_time == 0.5
    assert candidate.scarcity_evidence_ids == ["months", "days", "weeks"]

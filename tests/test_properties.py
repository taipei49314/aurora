"""Property-based tests (spec §28)."""
from __future__ import annotations

import pytest as _pytest
pytestmark = _pytest.mark.unit

from hypothesis import given, strategies as st

from aurora.features import cosine
from aurora.dedup import jaccard
from aurora.scoring import assemble, saturating
from aurora.config import ScoringConfig

_vec = st.dictionaries(st.text(min_size=1, max_size=5), st.floats(min_value=-10, max_value=10,
                                                                  allow_nan=False, allow_infinity=False),
                       max_size=8)


@given(_vec, _vec)
def test_cosine_bounded(a, b):
    c = cosine(a, b)
    assert -1.0001 <= c <= 1.0001


@given(_vec)
def test_cosine_self_is_one_or_zero(a):
    c = cosine(a, a)
    assert c == 0.0 or abs(c - 1.0) < 1e-6


@given(st.sets(st.integers(), max_size=10), st.sets(st.integers(), max_size=10))
def test_jaccard_symmetric_and_bounded(a, b):
    j1 = jaccard({str(x) for x in a}, {str(x) for x in b})
    j2 = jaccard({str(x) for x in b}, {str(x) for x in a})
    assert abs(j1 - j2) < 1e-9
    assert 0.0 <= j1 <= 1.0


@given(st.floats(min_value=0, max_value=1000, allow_nan=False), st.floats(min_value=0.01, max_value=100))
def test_saturating_bounded(value, target):
    assert 0.0 <= saturating(value, target) <= 100.0


@given(st.dictionaries(
    st.sampled_from(list(ScoringConfig().weights.keys())),
    st.floats(min_value=0, max_value=100, allow_nan=False), max_size=10))
def test_overall_score_always_bounded(components):
    comps = dict(components)
    comps.update({"hype_risk_score": 0, "contradiction_score": 0, "data_quality_penalty": 0})
    out = assemble(comps, ScoringConfig())
    assert 0.0 <= out["overall_score"] <= 100.0


@given(st.floats(min_value=0, max_value=100), st.floats(min_value=0, max_value=100))
def test_penalties_never_increase_score(hype, contra):
    cfg = ScoringConfig()
    base = {k: 55.0 for k in cfg.weights}
    base.update({"hype_risk_score": 0, "contradiction_score": 0, "data_quality_penalty": 0})
    penalized = dict(base, hype_risk_score=hype, contradiction_score=contra)
    assert assemble(penalized, cfg)["overall_score"] <= assemble(base, cfg)["overall_score"] + 1e-6

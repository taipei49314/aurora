"""Property-based tests (spec §28)."""
from __future__ import annotations

import time

import pytest as _pytest

pytestmark = _pytest.mark.unit

from hypothesis import given, settings, strategies as st

from aurora.features import cosine
from aurora.dedup import jaccard
from aurora.scoring import assemble, saturating
from aurora.config import ScoringConfig

# Cosine bounds depend on finite float values and shared-key overlap, not on
# the key alphabet. Use deterministic unique keys so generation stays cheap
# under load without shrinking the *semantic* counterexample space for values.
_floats = st.floats(min_value=-10, max_value=10, allow_nan=False, allow_infinity=False)


@st.composite
def _vec_unique_keys(draw):
    n = draw(st.integers(min_value=0, max_value=8))
    values = draw(st.lists(_floats, min_size=n, max_size=n))
    return {f"k{i}": v for i, v in enumerate(values)}


# Separate Unicode-key strategy: proves key *identity* (not ASCII restriction)
# is what matters — remapping labels must preserve cosine.
_unicode_keys = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=8,
)
_unicode_vec = st.dictionaries(_unicode_keys, _floats, max_size=8)


@settings(deadline=None, max_examples=200)
@given(_vec_unique_keys(), _vec_unique_keys())
def test_cosine_bounded(a, b):
    c = cosine(a, b)
    assert -1.0001 <= c <= 1.0001


@settings(deadline=None, max_examples=200)
@given(_vec_unique_keys())
def test_cosine_self_is_one_or_zero(a):
    c = cosine(a, a)
    assert c == 0.0 or abs(c - 1.0) < 1e-6


@settings(deadline=None, max_examples=100)
@given(_unicode_vec, _unicode_vec, st.integers())
def test_cosine_unicode_key_relabel_invariance(a, b, seed):
    """Relabeling keys with a bijection must not change cosine (key content irrelevant)."""
    keys = sorted(set(a) | set(b))
    # Deterministic bijection from seed
    relabel = {k: f"u{i}_{seed & 0xFFFF}" for i, k in enumerate(keys)}
    a2 = {relabel[k]: v for k, v in a.items()}
    b2 = {relabel[k]: v for k, v in b.items()}
    assert abs(cosine(a, b) - cosine(a2, b2)) < 1e-9


def test_cosine_performance_budget_deterministic():
    """deadline=None removes Hypothesis wall-clock flaking; keep an explicit budget.

    Builds two 256-dim sparse vectors and requires cosine < 50ms on a warm call.
    """
    a = {f"f{i}": float(i % 7) - 3.0 for i in range(256)}
    b = {f"f{i}": float((i * 3) % 11) - 5.0 for i in range(256)}
    # warm
    cosine(a, b)
    t0 = time.perf_counter()
    for _ in range(200):
        cosine(a, b)
    elapsed = time.perf_counter() - t0
    # 200 calls in < 50ms total is generous on CI; fails only on severe regressions.
    assert elapsed < 0.05, f"cosine budget exceeded: {elapsed:.4f}s for 200 calls"


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

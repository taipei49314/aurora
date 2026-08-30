"""Hype filter (spec §15).

Distinguishes genuine industry formation from narrative hype. A cluster with
huge news volume but no hiring/capex/supply-chain/customers and low source
independence gets a high hype-risk score, which the scorer subtracts. Loud
noise never raises the overall score by itself.

All sub-factors are in 0..1 (1 = maximally hype-like) and combined with
transparent weights.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from .models import (
    DEMAND_TYPES,
    NARRATIVE_TYPES,
    is_real_investment_observation,
)

_HYPE_WEIGHTS = {
    "narrative_dominance": 0.24,   # news/launches dominate real investment
    "low_real_investment": 0.20,
    "low_demand": 0.16,
    "low_independence": 0.18,
    "no_supply_chain": 0.10,
    "no_standards_or_contracts": 0.06,
    "faded": 0.06,
}

_FADE_WINDOW_COUNT = 3
_MIN_FADE_OBSERVATIONS = 6


def _parse_date(value):
    """Parse an ISO date without letting malformed/undated rows imply decay."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _fade_analysis(observations, as_of=None) -> dict:
    """Measure collapse over three equal-length calendar windows.

    ``as_of`` is the evaluation date (and should be the cutoff date for a
    historical run).  When omitted, the latest valid observation date keeps
    the original two-argument ``hype_assessment`` call deterministic and
    useful.  Undated/malformed observations never count toward the minimum,
    and dated observations after ``as_of`` never leak into the temporal
    factor.
    """
    parsed = []
    undated_count = 0
    for observation in observations:
        observed = _parse_date(observation.observed_at)
        if observed is None:
            undated_count += 1
        else:
            parsed.append(observed)

    explicit_as_of = as_of is not None
    anchor = _parse_date(as_of) if explicit_as_of else (max(parsed) if parsed else None)
    if explicit_as_of and anchor is None:
        raise ValueError(f"invalid hype as_of date: {as_of!r}")

    eligible = [observed for observed in parsed if anchor is not None and observed <= anchor]
    future_count = len(parsed) - len(eligible)
    base = {
        "score": 0.0,
        "as_of": anchor.isoformat() if anchor else None,
        "as_of_source": "explicit" if explicit_as_of else "latest_observation",
        "dated_observation_count": len(eligible),
        "undated_observation_count": undated_count,
        "excluded_after_as_of_count": future_count,
        "minimum_dated_observations": _MIN_FADE_OBSERVATIONS,
        "window_days": None,
        "window_counts": {"early": 0, "middle": 0, "recent": 0},
        "windows": [],
    }
    if anchor is None or len(eligible) < _MIN_FADE_OBSERVATIONS:
        return base

    # Anchor equal-length windows at the evaluation date.  Ceiling division
    # covers the complete earliest..as_of range while keeping all three
    # windows exactly the same number of calendar days.
    span_days = (anchor - min(eligible)).days + 1
    window_days = max(1, (span_days + _FADE_WINDOW_COUNT - 1) // _FADE_WINDOW_COUNT)
    names = ("early", "middle", "recent")
    counts = {name: 0 for name in names}
    for observed in eligible:
        age_days = (anchor - observed).days
        window_index = _FADE_WINDOW_COUNT - 1 - (age_days // window_days)
        # Ceiling division above guarantees coverage; clamp defensively for
        # unusual date subclasses while preserving deterministic behaviour.
        window_index = max(0, min(_FADE_WINDOW_COUNT - 1, window_index))
        counts[names[window_index]] += 1

    windows = []
    for index, name in enumerate(names):
        days_before_end = (_FADE_WINDOW_COUNT - 1 - index) * window_days
        end = anchor - timedelta(days=days_before_end)
        start = end - timedelta(days=window_days - 1)
        windows.append({
            "name": name,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "count": counts[name],
        })

    historical_peak = max(counts["early"], counts["middle"])
    faded = 0.0
    if historical_peak:
        faded = max(0.0, min(1.0, 1.0 - counts["recent"] / historical_peak))

    base.update({
        "score": round(faded, 4),
        "window_days": window_days,
        "window_counts": counts,
        "windows": windows,
    })
    return base


def _fade(observations, as_of=None) -> float:
    """Compatibility wrapper returning only the temporal fade score."""
    return _fade_analysis(observations, as_of=as_of)["score"]


def hype_assessment(cluster, observations, *, as_of=None) -> dict:
    """Assess narrative hype, optionally anchored at a historical cutoff.

    Existing callers may continue to pass only ``cluster`` and
    ``observations``.  Cutoff-aware callers should pass that cutoff as
    ``as_of`` so a quiet period up to the evaluation date remains visible.
    """
    obs = [o for o in observations if o.subject_entity in cluster]
    n = len(obs) or 1
    types = Counter(o.observation_type for o in obs)

    real = sum(1 for o in obs if is_real_investment_observation(o))
    demand = sum(types[t] for t in DEMAND_TYPES)
    narrative = sum(types[t] for t in NARRATIVE_TYPES) + types["NEWS_MENTION"] if "NEWS_MENTION" in types else sum(types[t] for t in NARRATIVE_TYPES)
    # count NEWS source-type observations as narrative too
    news_src = sum(1 for o in obs if o.metadata.get("source_type") == "NEWS")

    src_ids = [o.source_id for o in obs]
    indep_groups = {o.metadata.get("independence_group", o.source_id) for o in obs}
    independence_ratio = len(indep_groups) / (len(set(src_ids)) or 1)

    has_supply_chain = any(
        o.observation_type in {"SUPPLIER_RELATIONSHIP", "TECHNICAL_DEPENDENCY"}
        or (
            o.observation_type == "CAPACITY_EXPANSION"
            and is_real_investment_observation(o)
        )
        for o in obs
    )
    has_standards = any(o.observation_type in {"STANDARD_ACTIVITY", "REGULATORY_SUPPORT"} for o in obs)

    narrative_dominance = min(1.0, (narrative + news_src) / n / 0.6)  # saturates when >60% narrative
    low_real_investment = 1.0 - min(1.0, (real / n) / 0.3)
    low_demand = 1.0 - min(1.0, (demand / n) / 0.15)
    low_independence = 1.0 - min(1.0, independence_ratio / 0.6)
    fade = _fade_analysis(obs, as_of=as_of)
    factors = {
        "narrative_dominance": round(narrative_dominance, 4),
        "low_real_investment": round(low_real_investment, 4),
        "low_demand": round(low_demand, 4),
        "low_independence": round(low_independence, 4),
        "no_supply_chain": 0.0 if has_supply_chain else 1.0,
        "no_standards_or_contracts": 0.0 if has_standards else 1.0,
        "faded": fade["score"],
    }
    score = 100.0 * sum(_HYPE_WEIGHTS[k] * v for k, v in factors.items())
    return {
        "hype_risk_score": round(min(100.0, score), 2),
        "factors": factors,
        "weights": _HYPE_WEIGHTS,
        "independence_ratio": round(independence_ratio, 4),
        "real_investment_ratio": round(real / n, 4),
        "demand_ratio": round(demand / n, 4),
        "fade_analysis": fade,
    }

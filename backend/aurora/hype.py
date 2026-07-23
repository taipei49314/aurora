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

from .models import (
    REAL_INVESTMENT_TYPES, DEMAND_TYPES, NARRATIVE_TYPES,
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


def _fade(observations) -> float:
    """1.0 if activity spiked then collapsed in the most recent third."""
    dated = sorted([o for o in observations if o.observed_at], key=lambda o: o.observed_at)
    if len(dated) < 6:
        return 0.0
    third = len(dated) // 3
    early = third
    late = len(dated) - 2 * third
    # if the last third is much sparser than the first third -> faded
    if early == 0:
        return 0.0
    ratio = late / early
    return max(0.0, min(1.0, 1.0 - ratio))


def hype_assessment(cluster, observations) -> dict:
    obs = [o for o in observations if o.subject_entity in cluster]
    n = len(obs) or 1
    types = Counter(o.observation_type for o in obs)

    real = sum(types[t] for t in REAL_INVESTMENT_TYPES)
    demand = sum(types[t] for t in DEMAND_TYPES)
    narrative = sum(types[t] for t in NARRATIVE_TYPES) + types["NEWS_MENTION"] if "NEWS_MENTION" in types else sum(types[t] for t in NARRATIVE_TYPES)
    # count NEWS source-type observations as narrative too
    news_src = sum(1 for o in obs if o.metadata.get("source_type") == "NEWS")

    src_ids = [o.source_id for o in obs]
    indep_groups = {o.metadata.get("independence_group", o.source_id) for o in obs}
    independence_ratio = len(indep_groups) / (len(set(src_ids)) or 1)

    has_supply_chain = any(o.observation_type in {"SUPPLIER_RELATIONSHIP", "TECHNICAL_DEPENDENCY", "CAPACITY_EXPANSION"} for o in obs)
    has_standards = any(o.observation_type in {"STANDARD_ACTIVITY", "REGULATORY_SUPPORT"} for o in obs)

    narrative_dominance = min(1.0, (narrative + news_src) / n / 0.6)  # saturates when >60% narrative
    low_real_investment = 1.0 - min(1.0, (real / n) / 0.3)
    low_demand = 1.0 - min(1.0, (demand / n) / 0.15)
    low_independence = 1.0 - min(1.0, independence_ratio / 0.6)
    factors = {
        "narrative_dominance": round(narrative_dominance, 4),
        "low_real_investment": round(low_real_investment, 4),
        "low_demand": round(low_demand, 4),
        "low_independence": round(low_independence, 4),
        "no_supply_chain": 0.0 if has_supply_chain else 1.0,
        "no_standards_or_contracts": 0.0 if has_standards else 1.0,
        "faded": round(_fade(obs), 4),
    }
    score = 100.0 * sum(_HYPE_WEIGHTS[k] * v for k, v in factors.items())
    return {
        "hype_risk_score": round(min(100.0, score), 2),
        "factors": factors,
        "weights": _HYPE_WEIGHTS,
        "independence_ratio": round(independence_ratio, 4),
        "real_investment_ratio": round(real / n, 4),
        "demand_ratio": round(demand / n, 4),
    }

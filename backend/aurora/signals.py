"""Temporal signal detection (spec §11 time-acceleration, §15 hype timing).

For each entity we compute a reproducible signal summary from its observations:
strength (volume), acceleration (recent vs earlier activity), source diversity,
and independence. These feed both hypothesis scoring and the hype filter.

Acceleration compares the second half of the observed window to the first half.
A cluster that is genuinely forming shows rising real-investment activity, not a
single spike (which the hype filter separately penalizes).
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date

from .models import Observation, REAL_INVESTMENT_TYPES, NEGATIVE_TYPES
from .dedup import independent_sources_for


def _parse(d: str | None) -> date | None:
    if not d:
        return None
    try:
        return date.fromisoformat(d[:10])
    except ValueError:
        return None


def entity_signal_summary(observations, resolved_group) -> dict[str, dict]:
    """Return per-entity signal metrics keyed by entity_id."""
    by_entity: dict[str, list] = defaultdict(list)
    for o in observations:
        by_entity[o.subject_entity].append(o)

    out: dict[str, dict] = {}
    for eid, obs in by_entity.items():
        dated = [(_parse(o.observed_at), o) for o in obs]
        valid = [(d, o) for d, o in dated if d is not None]
        n = len(obs)
        strength = math.log1p(n) / math.log(50)  # ~1.0 around 50 obs
        # acceleration over the observed window
        acceleration = 0.0
        if len(valid) >= 4:
            valid.sort(key=lambda x: x[0])
            lo, hi = valid[0][0], valid[-1][0]
            span = (hi - lo).days or 1
            mid = lo.toordinal() + span / 2
            early = sum(1 for d, _ in valid if d.toordinal() <= mid)
            late = len(valid) - early
            acceleration = (late - early) / max(1, len(valid))  # -1..1
        src_ids = [o.source_id for o in obs]
        source_types = {o.metadata.get("source_type") for o in obs if o.metadata.get("source_type")}
        indep = independent_sources_for(src_ids, resolved_group)
        raw = len(set(src_ids)) or 1
        real_inv = sum(1 for o in obs if o.observation_type in REAL_INVESTMENT_TYPES)
        negative = sum(1 for o in obs if o.observation_type in NEGATIVE_TYPES)
        out[eid] = {
            "observation_count": n,
            "strength": min(1.0, strength),
            "acceleration": max(-1.0, min(1.0, acceleration)),
            "source_diversity": len(source_types),
            "independent_sources": indep,
            "raw_sources": raw,
            "independence_score": indep / raw,
            "real_investment_count": real_inv,
            "negative_count": negative,
        }
    return out

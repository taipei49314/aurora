"""Evidence + counterevidence engine (spec §16).

Every hypothesis must actively collect disconfirming evidence, list what is
missing, and state the conditions under which it would be falsified. A cluster
with no counterevidence analysis may never become an INDUSTRY_CANDIDATE.

Counterevidence is drawn from real negative observations (cancellations,
shutdowns, cost/lead-time pressure) plus structural red flags (single-entity
domination, temporal collapse).
"""
from __future__ import annotations

from collections import Counter

from .models import OBSERVATION_TYPES, NEGATIVE_TYPES, REAL_INVESTMENT_TYPES, DEMAND_TYPES

# observation types we EXPECT a genuine forming industry to eventually show
_EXPECTED_TYPES = [
    "PATENT_ACTIVITY", "HIRING_ACTIVITY", "CAPEX_ACTIVITY", "SUPPLIER_RELATIONSHIP",
    "CUSTOMER_RELATIONSHIP", "STANDARD_ACTIVITY", "ADOPTION_SIGNAL",
]


def analyze(cluster, observations, dedup_resolved_group) -> dict:
    obs = [o for o in observations if o.subject_entity in cluster]
    types = Counter(o.observation_type for o in obs)

    supporting = [o for o in obs if o.observation_type in (REAL_INVESTMENT_TYPES | DEMAND_TYPES)]
    supporting.sort(key=lambda o: (-(o.confidence or 0), o.observation_id))
    counter = [o for o in obs if o.observation_type in NEGATIVE_TYPES]
    counter.sort(key=lambda o: (-(o.confidence or 0), o.observation_id))

    # structural red flag: single-entity domination
    subj_counts = Counter(o.subject_entity for o in obs)
    dominant_share = (subj_counts.most_common(1)[0][1] / len(obs)) if obs else 0.0
    single_entity_driven = dominant_share > 0.7 and len(cluster) >= 2

    # contradiction score: weight of negative observations + structural penalty
    neg = len(counter)
    total = len(obs) or 1
    contradiction = 100.0 * min(1.0, (neg / total) / 0.25)
    if single_entity_driven:
        contradiction = max(contradiction, 55.0)

    missing = [t for t in _EXPECTED_TYPES if types.get(t, 0) == 0]

    disconfirmation = [
        "Key suppliers exit or capacity expansion is cancelled.",
        "Hiring for the core capability stops or reverses for >12 months.",
        "Announced customer adoptions fail to convert to repeat purchases.",
        "A substitute technology displaces the core dependency.",
        "Cost/lead-time pressure persists with no path to scale economics.",
        "Signals prove to be driven by a single entity with no independent followers.",
    ]

    return {
        "contradiction_score": round(contradiction, 2),
        "strongest_supporting_evidence": [o.observation_id for o in supporting[:5]],
        "strongest_counterevidence": [o.observation_id for o in counter[:5]],
        "missing_evidence": missing,
        "disconfirmation_conditions": disconfirmation,
        "single_entity_driven": single_entity_driven,
        "dominant_entity_share": round(dominant_share, 4),
        "negative_observation_count": neg,
    }

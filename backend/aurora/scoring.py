"""Transparent hypothesis scoring (spec §14).

There is no mysterious AI score. ``overall`` is a documented linear combination
of 0..100 component scores minus explicit penalties, all driven by
``ScoringConfig``. The returned explanation records every input, weight and
contribution so the UI can show exactly why a hypothesis scored what it did.
"""
from __future__ import annotations

from .config import ScoringConfig


def saturating(value: float, target: float) -> float:
    """Map a raw ratio to 0..100, saturating at ``target``."""
    if target <= 0:
        return 0.0
    return 100.0 * min(1.0, value / target)


def assemble(components: dict, cfg: ScoringConfig) -> dict:
    """components: mapping of component_name -> 0..100 score, plus the three
    penalty inputs (hype_risk_score, contradiction_score, data_quality_penalty).
    """
    contributions = {}
    weighted_sum = 0.0
    for name, weight in cfg.weights.items():
        score = float(components.get(name, 0.0))
        contribution = weight * score
        contributions[name] = {"score": round(score, 2), "weight": weight, "contribution": round(contribution, 2)}
        weighted_sum += contribution

    hype = float(components.get("hype_risk_score", 0.0))
    contradiction = float(components.get("contradiction_score", 0.0))
    dq = float(components.get("data_quality_penalty", 0.0))

    hype_pen = cfg.hype_penalty_weight * (hype / 100.0) * weighted_sum
    contra_pen = cfg.contradiction_penalty_weight * (contradiction / 100.0) * weighted_sum
    dq_pen = cfg.data_quality_penalty_weight * dq

    overall = weighted_sum - hype_pen - contra_pen - dq_pen
    overall = max(0.0, min(100.0, overall))

    if overall >= 70:
        band = "HIGH"
    elif overall >= 50:
        band = "MEDIUM"
    elif overall >= 30:
        band = "LOW"
    else:
        band = "VERY_LOW"

    return {
        "overall_score": round(overall, 2),
        "confidence_band": band,
        "weighted_sum": round(weighted_sum, 2),
        "penalties": {
            "hype": round(hype_pen, 2),
            "contradiction": round(contra_pen, 2),
            "data_quality": round(dq_pen, 2),
        },
        "contributions": contributions,
        "formula": "overall = clip( sum(w_i*score_i) - hype_pen - contradiction_pen - dq_pen , 0, 100 )",
    }

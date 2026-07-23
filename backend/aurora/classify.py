"""Hypothesis classification (spec §3, §12, §15, §16).

Turns scores + structural gates into a status. The order of checks matters:
insufficient evidence and existing-variant are decided BEFORE we ever consider
calling something an industry candidate, and hype/counterevidence can only
downgrade, never upgrade.
"""
from __future__ import annotations

from .config import ClassificationConfig


def classify(*, independent_sources: int, distinct_source_types: int, n_entities: int,
             taxonomy_similarity: float, straddles_two: bool, hype_risk: float,
             contradiction: float, cluster_stability: float, overall: float,
             value_chain: float, real_investment: float, demand: float,
             cfg: ClassificationConfig) -> tuple[str, list[str]]:
    reasons: list[str] = []

    # 1. hard evidence gate -> insufficient. This is about *genuine sparsity /
    # single-entity domination*: too few entities, or too few INDEPENDENT
    # sources (a single giant syndicating its own PR collapses to ~1 group).
    # Source-type diversity is NOT part of this gate — a loud mono-source-type
    # cluster is better described as HYPE (checked below), not "insufficient".
    if n_entities < cfg.min_entities or independent_sources < cfg.min_independent_sources:
        reasons.append(
            f"insufficient independent cross-entity support "
            f"(indep_sources={independent_sources}, entities={n_entities})")
        return "INSUFFICIENT_EVIDENCE", reasons

    # 2. existing-industry variant: high similarity to a known industry, and NOT
    # a genuine cross-domain straddle
    if taxonomy_similarity >= cfg.existing_variant_similarity and not straddles_two:
        reasons.append(f"high similarity ({taxonomy_similarity:.2f}) to an existing industry")
        return "EXISTING_INDUSTRY_VARIANT", reasons

    # 3. counterevidence dominates -> rejected/dormant (downgrade only)
    if contradiction >= cfg.contradiction_reject:
        reasons.append(f"counterevidence dominates (contradiction={contradiction:.0f})")
        return "REJECTED", reasons
    if contradiction >= cfg.contradiction_dormant:
        reasons.append(f"significant counterevidence / collapse (contradiction={contradiction:.0f})")
        return "DORMANT", reasons

    # 4. hype -> hype cluster (loud but hollow)
    if hype_risk >= cfg.hype_risk_threshold:
        reasons.append(f"hype risk high ({hype_risk:.0f}) with weak real investment/demand")
        return "HYPE_CLUSTER", reasons

    # 5. unstable clusters cannot be candidates
    if cluster_stability * 100 < 55:
        reasons.append(f"cluster unstable (stability={cluster_stability:.2f})")
        return "EMERGING_CAPABILITY_CLUSTER", reasons

    # 6. industry candidate: needs overall + structural completeness + genuine
    # cross-source support (>= 2 distinct source types).
    if (overall >= cfg.candidate_min_overall and
            value_chain >= cfg.candidate_min_value_chain and
            real_investment >= cfg.candidate_min_real_investment and
            demand >= cfg.candidate_min_demand and
            distinct_source_types >= cfg.min_distinct_source_types):
        reasons.append("meets candidate thresholds on overall, value chain, real investment, demand and cross-source diversity")
        return "INDUSTRY_CANDIDATE", reasons

    # 7. emerging capability cluster
    if overall >= cfg.emerging_min_overall:
        reasons.append("coherent emerging capability cluster, not yet a full candidate")
        return "EMERGING_CAPABILITY_CLUSTER", reasons

    reasons.append("below emerging threshold")
    return "INSUFFICIENT_EVIDENCE", reasons

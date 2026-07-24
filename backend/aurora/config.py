"""Engine, scoring and classification configuration (spec §14, §22).

Every number that influences a result lives here so that (a) the scoring formula
is fully transparent and explainable, and (b) changing a weight forces a new
Research Run rather than silently mutating history. Nothing in the engine may
hardcode an industry name, keyword or threshold outside this file.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

ENGINE_VERSION = "0.1.28"
FEATURE_VERSION = "0.1.28"
TAXONOMY_VERSION = "2024.1"


@dataclass(frozen=True)
class ScoringConfig:
    """Weights for the overall-score linear combination.

    overall = clip( sum(w_i * score_i) - penalties , 0, 100 )
    Weights are expressed as fractions; positive weights sum to 1.0 so the
    weighted sum is itself on a 0..100 scale before penalties.
    """
    version: str = "0.1.0"
    weights: dict = field(default_factory=lambda: {
        "novelty_score": 0.10,
        "coherence_score": 0.14,
        "acceleration_score": 0.10,
        "value_chain_score": 0.12,
        "real_investment_score": 0.16,
        "demand_score": 0.12,
        "bottleneck_score": 0.06,
        "naming_gap_score": 0.08,
        "source_independence_score": 0.08,
        "cluster_stability_score": 0.04,
    })
    # penalties are subtracted after the weighted sum
    hype_penalty_weight: float = 0.45
    contradiction_penalty_weight: float = 0.40
    data_quality_penalty_weight: float = 1.0


@dataclass(frozen=True)
class ClassificationConfig:
    """Thresholds that turn scores + structural gates into a status (spec §3)."""
    # minimum independent evidence to be anything more than a seed
    min_independent_sources: int = 3
    min_distinct_source_types: int = 2
    min_entities: int = 3
    # existing-industry-variant: high similarity to a known industry.
    # Calibrated on Northstar: rebranded-mature clusters sit ~0.55-0.62 while
    # genuinely-new clusters sit <0.05, so 0.50 cleanly separates them.
    existing_variant_similarity: float = 0.50
    # hype gate
    hype_risk_threshold: float = 60.0
    # emerging vs candidate
    emerging_min_overall: float = 45.0
    candidate_min_overall: float = 62.0
    candidate_min_value_chain: float = 45.0
    candidate_min_real_investment: float = 40.0
    candidate_min_demand: float = 30.0
    # dormant/rejected via counterevidence
    contradiction_dormant: float = 45.0
    contradiction_reject: float = 70.0


@dataclass(frozen=True)
class ClusterConfig:
    random_seed: int = 20240115
    # feature-space agglomerative clustering
    similarity_threshold: float = 0.18   # cosine sim to link two entities
    min_cluster_size: int = 3
    # graph community detection (label propagation)
    label_propagation_max_iter: int = 100
    edge_min_weight: float = 0.12
    # stability: fraction of bootstrap runs an entity keeps its cluster
    stability_bootstrap: int = 8
    stability_drop_fraction: float = 0.15
    min_stability: float = 0.55


@dataclass(frozen=True)
class EngineConfig:
    engine_version: str = ENGINE_VERSION
    feature_version: str = FEATURE_VERSION
    taxonomy_version: str = TAXONOMY_VERSION
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    classification: ClassificationConfig = field(default_factory=ClassificationConfig)
    clustering: ClusterConfig = field(default_factory=ClusterConfig)

    def manifest(self) -> dict:
        return {
            "engine_version": self.engine_version,
            "feature_version": self.feature_version,
            "taxonomy_version": self.taxonomy_version,
            "scoring": asdict(self.scoring),
            "classification": asdict(self.classification),
            "clustering": asdict(self.clustering),
        }


DEFAULT_CONFIG = EngineConfig()

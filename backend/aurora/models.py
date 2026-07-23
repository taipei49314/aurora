"""Core data model (spec §6).

Implemented as plain dataclasses rather than SQLAlchemy rows so the discovery
engine can run fully in-memory and offline with zero third-party runtime deps.
A JSON snapshot store (see ``store.py``) provides persistence. SQLAlchemy/SQLite
is the intended production persistence layer and is tracked as PARTIAL in the
self-audit.

Enum values are kept as plain string constants (not ``enum.Enum``) so that
serialized snapshots are trivially diffable and stable across Python versions.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# --- controlled vocabularies (spec §6) -------------------------------------

SOURCE_TYPES = [
    "COMPANY_FILING", "PATENT", "PAPER", "JOB_POSTING", "NEWS",
    "GOVERNMENT_PROGRAM", "STANDARD", "RESEARCH_NOTE",
]

ENTITY_TYPES = [
    "COMPANY", "RESEARCH_INSTITUTE", "UNIVERSITY", "GOVERNMENT", "STANDARD_BODY",
    "PRODUCT", "TECHNOLOGY", "MATERIAL", "COMPONENT", "PROCESS", "FACILITY",
    "APPLICATION", "MARKET",
]

OBSERVATION_TYPES = [
    "PATENT_ACTIVITY", "HIRING_ACTIVITY", "CAPEX_ACTIVITY", "CAPACITY_EXPANSION",
    "PRODUCT_LAUNCH", "TECHNICAL_DEPENDENCY", "SUPPLIER_RELATIONSHIP",
    "CUSTOMER_RELATIONSHIP", "STRATEGIC_INVESTMENT", "STANDARD_ACTIVITY",
    "RESEARCH_ACTIVITY", "PRICE_PRESSURE", "LEAD_TIME_PRESSURE",
    "REGULATORY_SUPPORT", "ADOPTION_SIGNAL", "DEMAND_SIGNAL",
    "CANCELLATION_SIGNAL", "SHUTDOWN_SIGNAL",
]

# observation types that represent *real physical/economic investment* rather
# than mere narrative. Used by the hype filter and real-investment score.
REAL_INVESTMENT_TYPES = {
    "PATENT_ACTIVITY", "HIRING_ACTIVITY", "CAPEX_ACTIVITY", "CAPACITY_EXPANSION",
    "SUPPLIER_RELATIONSHIP", "STANDARD_ACTIVITY",
}
DEMAND_TYPES = {"CUSTOMER_RELATIONSHIP", "ADOPTION_SIGNAL", "DEMAND_SIGNAL"}
NARRATIVE_TYPES = {"PRODUCT_LAUNCH", "STRATEGIC_INVESTMENT"}
NEGATIVE_TYPES = {"CANCELLATION_SIGNAL", "SHUTDOWN_SIGNAL", "PRICE_PRESSURE", "LEAD_TIME_PRESSURE"}

HYPOTHESIS_STATUS = [
    "SEED", "EMERGING_CAPABILITY_CLUSTER", "INDUSTRY_CANDIDATE",
    "EXISTING_INDUSTRY_VARIANT", "HYPE_CLUSTER", "DORMANT", "REJECTED",
    "INSUFFICIENT_EVIDENCE",
]

VALUE_CHAIN_ROLES = [
    "RAW_INPUT", "CORE_COMPONENT", "ENABLING_EQUIPMENT", "PROCESS",
    "INTEGRATION", "INFRASTRUCTURE", "DISTRIBUTION", "APPLICATION",
    "END_CUSTOMER", "STANDARD_OR_REGULATION",
]

EVIDENCE_RELATIONSHIPS = ["SUPPORTS", "CONTRADICTS", "WEAKENS", "DUPLICATES", "CONTEXT_ONLY"]

RELIABILITY_TIERS = ["A", "B", "C", "D"]  # A official / B reproducible / C news / D social


@dataclass
class Source:
    source_id: str
    source_type: str
    publisher: str
    title: str
    published_at: Optional[str]          # ISO date or None (missing dates are allowed but flagged)
    retrieved_at: str
    url_or_local_path: str
    content_hash: str
    independence_group: str              # sources sharing this id are NOT independent
    reliability_tier: str
    language: str
    # Patent / document family for independence (also accepted under metadata.family_id)
    family_id: str = ""
    # Activity / filing / application date (dual-date with published_at; metadata.event_date fallback)
    event_date: Optional[str] = None
    # Real-world event key for event-level independence (metadata.event_id fallback)
    event_id: str = ""
    # Outlet identity for independence (metadata fallback; engine 0.1.12+)
    outlet_domain: str = ""
    wire_id: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class Entity:
    entity_id: str
    entity_type: str
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    country: str = ""
    created_at: str = ""
    # Cross-dump joins: [{system, id}, ...] — also accepted under metadata.external_ids at import
    external_ids: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class Observation:
    observation_id: str
    source_id: str
    observed_at: Optional[str]
    observation_type: str
    subject_entity: str
    object_entity: Optional[str]
    numeric_value: Optional[float]
    unit: Optional[str]
    text_excerpt: str
    confidence: float
    # Real-world event key (top-level or metadata; may inherit from Source.event_id)
    event_id: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class Signal:
    signal_id: str
    signal_type: str
    entity_ids: list[str]
    start_date: Optional[str]
    end_date: Optional[str]
    strength: float
    acceleration: float
    source_diversity: int
    independence_score: float
    calculation_method: str
    observation_ids: list[str]


@dataclass
class EvidenceLink:
    evidence_id: str
    hypothesis_id: str
    observation_id: str
    relationship: str
    support_strength: float
    reason: str


@dataclass
class ValueChainNode:
    value_chain_node_id: str
    hypothesis_id: str
    entity_id: str
    role: str
    criticality: float
    substitutability: float
    dependency_count: int
    capacity_constraint: float
    lead_time_constraint: float
    evidence_ids: list[str] = field(default_factory=list)
    confidence_flag: str = "CONFIRMED"   # or INFERRED_LOW_CONFIDENCE (spec §17)


@dataclass
class BottleneckCandidate:
    entity_id: str
    hypothesis_id: str
    bottleneck_score: float
    centrality: float
    supplier_concentration: float
    substitutability: float
    lead_time: float
    capacity_constraint: float
    cross_cluster_dependency: float
    failure_impact: float
    evidence_confidence: float
    limits_what: str
    downstream_dependents: list[str]
    substitute_exists: bool
    substitution_time_note: str
    scarcity_evidence_ids: list[str]
    disconfirming_data_note: str


@dataclass
class Hypothesis:
    hypothesis_id: str
    generated_name: str
    human_name: Optional[str]
    status: str
    summary: str
    created_from_run: str
    first_detected_at: Optional[str]
    # scores 0..100
    novelty_score: float = 0.0
    coherence_score: float = 0.0
    acceleration_score: float = 0.0
    value_chain_score: float = 0.0
    real_investment_score: float = 0.0
    demand_score: float = 0.0
    bottleneck_score: float = 0.0
    hype_risk_score: float = 0.0
    contradiction_score: float = 0.0
    naming_gap_score: float = 0.0
    source_independence_score: float = 0.0
    cluster_stability_score: float = 0.0
    data_quality_penalty: float = 0.0
    overall_score: float = 0.0
    confidence_band: str = "LOW"
    entity_ids: list[str] = field(default_factory=list)
    observation_ids: list[str] = field(default_factory=list)
    score_explanation: dict = field(default_factory=dict)
    strongest_supporting_evidence: list[str] = field(default_factory=list)
    strongest_counterevidence: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    disconfirmation_conditions: list[str] = field(default_factory=list)
    existing_industry_similarity: dict = field(default_factory=dict)
    cluster_method: str = ""


def to_dict(obj: Any) -> Any:
    """asdict wrapper that also handles lists of dataclasses."""
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return asdict(obj)

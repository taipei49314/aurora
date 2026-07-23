"""Value-chain construction (spec §17).

Roles are assigned from entity type + the observation types an entity
participates in. Edges come from real relational observations and each carries
the evidence (observation ids) that justifies it. Edges that are only inferred
from co-occurrence — never asserted by a source — are flagged
INFERRED_LOW_CONFIDENCE and never shown as confirmed fact.
"""
from __future__ import annotations

from collections import defaultdict

from .ids import prefixed_id
from .models import ValueChainNode

_TYPE_TO_ROLE = {
    "MATERIAL": "RAW_INPUT",
    "COMPONENT": "CORE_COMPONENT",
    "TECHNOLOGY": "CORE_COMPONENT",
    "FACILITY": "ENABLING_EQUIPMENT",
    "PROCESS": "PROCESS",
    "PRODUCT": "INTEGRATION",
    "COMPANY": "INTEGRATION",
    "APPLICATION": "APPLICATION",
    "MARKET": "END_CUSTOMER",
    "STANDARD_BODY": "STANDARD_OR_REGULATION",
    "GOVERNMENT": "STANDARD_OR_REGULATION",
    # PERSON is not an industry value-chain role; if present, keep low-profile
    "PERSON": "INTEGRATION",
    "RESEARCH_INSTITUTE": "INTEGRATION",
    "UNIVERSITY": "INTEGRATION",
}

# roles that a reasonably complete chain should cover
_COMPLETENESS_ROLES = [
    "RAW_INPUT", "CORE_COMPONENT", "ENABLING_EQUIPMENT", "PROCESS",
    "INTEGRATION", "APPLICATION", "END_CUSTOMER",
]


def _role_for(entity, obs_types) -> str:
    role = _TYPE_TO_ROLE.get(entity.entity_type, "INTEGRATION")
    # equipment purchase / capex signals promote a company toward INFRASTRUCTURE
    if "CAPACITY_EXPANSION" in obs_types and entity.entity_type == "COMPANY":
        role = "INFRASTRUCTURE"
    return role


def build(hypothesis_id, cluster, entities, observations):
    by_id = {e.entity_id: e for e in entities}
    obs_by_subject = defaultdict(list)
    for o in observations:
        if o.subject_entity in cluster:
            obs_by_subject[o.subject_entity].append(o)

    nodes = []
    for eid in sorted(cluster):
        e = by_id.get(eid)
        if not e:
            continue
        etypes = {o.observation_type for o in obs_by_subject.get(eid, [])}
        role = _role_for(e, etypes)
        ev = [o.observation_id for o in obs_by_subject.get(eid, [])]
        nodes.append(ValueChainNode(
            value_chain_node_id=prefixed_id("vcn", hypothesis_id, eid),
            hypothesis_id=hypothesis_id,
            entity_id=eid,
            role=role,
            criticality=0.0,       # filled by bottleneck analysis
            substitutability=1.0,
            dependency_count=0,
            capacity_constraint=0.0,
            lead_time_constraint=0.0,
            evidence_ids=ev,
        ))

    # edges from relational observations
    edges = []
    for o in observations:
        if o.subject_entity in cluster and o.object_entity in cluster and o.observation_type in {
            "SUPPLIER_RELATIONSHIP", "TECHNICAL_DEPENDENCY", "CUSTOMER_RELATIONSHIP",
        }:
            edges.append({
                "from": o.object_entity if o.observation_type != "CUSTOMER_RELATIONSHIP" else o.subject_entity,
                "to": o.subject_entity if o.observation_type != "CUSTOMER_RELATIONSHIP" else o.object_entity,
                "relation": o.observation_type,
                "evidence_ids": [o.observation_id],
                "confidence_flag": "CONFIRMED",
            })

    roles_present = {n.role for n in nodes}
    completeness = len(roles_present & set(_COMPLETENESS_ROLES)) / len(_COMPLETENESS_ROLES)
    return {
        "nodes": nodes,
        "edges": edges,
        "roles_present": sorted(roles_present),
        "value_chain_score": round(100.0 * completeness, 2),
    }

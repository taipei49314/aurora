"""Focused regressions for value-chain roles, edges, and provenance."""
from __future__ import annotations

import pytest

from aurora.models import ENTITY_TYPES, Entity, Observation
from aurora.value_chain import build


pytestmark = pytest.mark.unit


ENTITY_ROLE_CASES = [
    ("COMPANY", "INTEGRATION"),
    ("RESEARCH_INSTITUTE", "INTEGRATION"),
    ("UNIVERSITY", "INTEGRATION"),
    ("GOVERNMENT", "STANDARD_OR_REGULATION"),
    ("STANDARD_BODY", "STANDARD_OR_REGULATION"),
    ("PRODUCT", "INTEGRATION"),
    ("TECHNOLOGY", "CORE_COMPONENT"),
    ("MATERIAL", "RAW_INPUT"),
    ("COMPONENT", "CORE_COMPONENT"),
    ("PROCESS", "PROCESS"),
    ("FACILITY", "ENABLING_EQUIPMENT"),
    ("APPLICATION", "APPLICATION"),
    ("MARKET", "END_CUSTOMER"),
    ("PERSON", "INTEGRATION"),
    ("PROVISIONAL", "INTEGRATION"),
]


def _entity(entity_id: str, entity_type: str) -> Entity:
    return Entity(
        entity_id=entity_id,
        entity_type=entity_type,
        canonical_name=entity_id.replace("-", " ").title(),
    )


def _observation(
    observation_id: str,
    observation_type: str,
    *,
    subject: str,
    object_entity: str | None = None,
    numeric_value: float | None = None,
) -> Observation:
    return Observation(
        observation_id=observation_id,
        source_id=f"source-{observation_id}",
        observed_at="2026-01-01",
        observation_type=observation_type,
        subject_entity=subject,
        object_entity=object_entity,
        numeric_value=numeric_value,
        unit=None,
        text_excerpt=observation_id,
        confidence=1.0,
    )


def test_role_cases_cover_every_controlled_entity_type():
    assert {entity_type for entity_type, _ in ENTITY_ROLE_CASES} == set(ENTITY_TYPES)


@pytest.mark.parametrize(("entity_type", "expected_role"), ENTITY_ROLE_CASES)
def test_entity_type_maps_to_expected_role(entity_type, expected_role):
    entity = _entity("entity", entity_type)

    result = build("hypothesis", [entity.entity_id], [entity], [])

    assert len(result["nodes"]) == 1
    assert result["nodes"][0].role == expected_role


@pytest.mark.parametrize(
    ("numeric_value", "expected_role"),
    [
        (-1, "INTEGRATION"),
        (None, "INFRASTRUCTURE"),
        (0, "INFRASTRUCTURE"),
        (1, "INFRASTRUCTURE"),
    ],
)
def test_capacity_expansion_sign_controls_company_role(numeric_value, expected_role):
    company = _entity("company", "COMPANY")
    capacity = _observation(
        "capacity",
        "CAPACITY_EXPANSION",
        subject=company.entity_id,
        numeric_value=numeric_value,
    )

    result = build("hypothesis", [company.entity_id], [company], [capacity])

    assert result["nodes"][0].role == expected_role
    assert result["nodes"][0].evidence_ids == [capacity.observation_id]


@pytest.mark.parametrize(
    ("relationship", "expected_from", "expected_to"),
    [
        ("SUPPLIER_RELATIONSHIP", "upstream", "downstream"),
        ("TECHNICAL_DEPENDENCY", "upstream", "downstream"),
        ("CUSTOMER_RELATIONSHIP", "downstream", "upstream"),
    ],
)
def test_confirmed_relationship_edge_direction_and_provenance(
    relationship,
    expected_from,
    expected_to,
):
    upstream = _entity("upstream", "COMPONENT")
    downstream = _entity("downstream", "PRODUCT")
    observation = _observation(
        "relationship-evidence",
        relationship,
        subject="downstream",
        object_entity="upstream",
    )

    result = build(
        "hypothesis",
        ["upstream", "downstream"],
        [upstream, downstream],
        [observation],
    )

    assert result["edges"] == [
        {
            "from": expected_from,
            "to": expected_to,
            "relation": relationship,
            "evidence_ids": [observation.observation_id],
            "confidence_flag": "CONFIRMED",
        }
    ]
    nodes = {node.entity_id: node for node in result["nodes"]}
    assert nodes["downstream"].evidence_ids == [observation.observation_id]
    assert nodes["downstream"].confidence_flag == "CONFIRMED"
    assert nodes["upstream"].evidence_ids == []


@pytest.mark.parametrize(
    ("subject", "object_entity"),
    [
        ("inside", "outside"),
        ("outside", "inside"),
    ],
)
@pytest.mark.parametrize(
    "relationship_type",
    [
        "SUPPLIER_RELATIONSHIP",
        "TECHNICAL_DEPENDENCY",
        "CUSTOMER_RELATIONSHIP",
    ],
)
def test_relationship_with_endpoint_outside_cluster_does_not_create_edge(
    subject,
    object_entity,
    relationship_type,
):
    inside = _entity("inside", "COMPANY")
    outside = _entity("outside", "COMPONENT")
    relationship = _observation(
        "cross-cluster-relationship",
        relationship_type,
        subject=subject,
        object_entity=object_entity,
    )

    result = build("hypothesis", ["inside"], [inside, outside], [relationship])

    assert result["edges"] == []


def test_infrastructure_promotion_preserves_complete_chain_coverage():
    entities = [
        _entity("material", "MATERIAL"),
        _entity("component", "COMPONENT"),
        _entity("facility", "FACILITY"),
        _entity("process", "PROCESS"),
        _entity("company", "COMPANY"),
        _entity("application", "APPLICATION"),
        _entity("market", "MARKET"),
    ]
    cluster = [entity.entity_id for entity in entities]
    baseline = build("hypothesis", cluster, entities, [])
    capacity = _observation(
        "capacity",
        "CAPACITY_EXPANSION",
        subject="company",
        numeric_value=1,
    )

    promoted = build("hypothesis", cluster, entities, [capacity])

    assert baseline["value_chain_score"] == 100.0
    assert promoted["value_chain_score"] == baseline["value_chain_score"]
    assert "INTEGRATION" in baseline["roles_present"]
    assert "INFRASTRUCTURE" in promoted["roles_present"]
    assert "INTEGRATION" not in promoted["roles_present"]

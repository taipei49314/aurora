"""Unit tests for aurora.provisional helpers and filter semantics (0.1.42+)."""
from __future__ import annotations

import pytest

from aurora import import_package
from aurora.models import Entity, Observation
from aurora.provisional import (
    is_provisional_entity,
    observation_has_provisional_mention,
    observation_object_provisional,
    observation_subject_provisional,
)


@pytest.mark.unit
def test_is_provisional_entity_type_and_metadata():
    assert is_provisional_entity(
        Entity(entity_id="e1", entity_type="PROVISIONAL", canonical_name="X")
    )
    assert is_provisional_entity(
        Entity(
            entity_id="e2",
            entity_type="COMPANY",
            canonical_name="Y",
            metadata={"provisional": True},
        )
    )
    assert not is_provisional_entity(
        Entity(entity_id="e3", entity_type="COMPANY", canonical_name="Z")
    )
    assert is_provisional_entity(
        {"entity_type": "PROVISIONAL", "canonical_name": "D", "metadata": {}}
    )
    assert not is_provisional_entity(None)


@pytest.mark.unit
def test_observation_provisional_flags():
    o = Observation(
        observation_id="o1",
        source_id="s1",
        observed_at="2020-01-01",
        observation_type="HIRING_ACTIVITY",
        subject_entity="e1",
        object_entity="e2",
        numeric_value=None,
        unit=None,
        text_excerpt="x",
        confidence=0.7,
        metadata={"subject_provisional": True, "object_provisional": True},
    )
    assert observation_subject_provisional(o)
    assert observation_object_provisional(o)
    assert observation_has_provisional_mention(o)
    assert observation_subject_provisional({"metadata": {"subject_provisional": True}})
    assert not observation_subject_provisional({"metadata": {}})


@pytest.mark.unit
def test_import_stage_sets_flags_detectable_by_helpers():
    pkg = {
        "stage_unresolved": True,
        "entities": [],
        "sources": [
            {
                "ref": "s1",
                "source_type": "NEWS",
                "publisher": "Wire",
                "title": "T",
                "published_at": "2020-01-01",
            }
        ],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "HIRING_ACTIVITY",
                "subject": "Ghost Co",
                "observed_at": "2020-01-01",
                "text_excerpt": "hiring",
            }
        ],
    }
    snap = import_package(pkg)
    assert len(snap.entities) == 1
    assert is_provisional_entity(snap.entities[0])
    assert observation_subject_provisional(snap.observations[0])
    # filter semantics used by API
    ents = [e for e in snap.entities if is_provisional_entity(e)]
    assert len(ents) == 1
    resolved = [e for e in snap.entities if not is_provisional_entity(e)]
    assert resolved == []

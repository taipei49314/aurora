"""Opt-in provisional entities for unresolved mentions (engine 0.1.39+)."""
from __future__ import annotations

import pytest

from aurora import import_package
from aurora.clustering import CLUSTERABLE_TYPES, feature_space_clusters
from aurora.config import DEFAULT_CONFIG
from aurora.entity_resolution import EntityResolver


@pytest.mark.unit
def test_unresolved_still_fails_without_stage_flag():
    pkg = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Known Co"}],
        "sources": [
            {
                "ref": "s1",
                "source_type": "NEWS",
                "publisher": "Wire",
                "title": "Note",
                "published_at": "2020-01-01",
            }
        ],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "HIRING_ACTIVITY",
                "subject": "Unknown Startup LLC",
                "observed_at": "2020-01-01",
                "text_excerpt": "hiring",
            }
        ],
    }
    snap = import_package(pkg)
    assert snap.observations == []
    assert any(e.get("error_code") == "ENTITY_RESOLUTION_AMBIGUOUS" for e in snap.import_errors)
    assert snap.counts.get("provisional_entities", 0) == 0


@pytest.mark.unit
def test_package_stage_unresolved_creates_provisional():
    pkg = {
        "stage_unresolved": True,
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Known Co"}],
        "sources": [
            {
                "ref": "s1",
                "source_type": "NEWS",
                "publisher": "Wire",
                "title": "Note",
                "published_at": "2020-01-01",
            }
        ],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "HIRING_ACTIVITY",
                "subject": "Unknown Startup LLC",
                "observed_at": "2020-01-01",
                "text_excerpt": "hiring",
            }
        ],
    }
    snap = import_package(pkg)
    assert len(snap.observations) == 1
    obs = snap.observations[0]
    assert obs.subject_raw == "Unknown Startup LLC"
    assert obs.metadata.get("subject_provisional") is True
    prov = next(e for e in snap.entities if e.canonical_name == "Unknown Startup LLC")
    assert prov.entity_type == "PROVISIONAL"
    assert prov.metadata.get("provisional") is True
    assert snap.counts.get("provisional_entities") == 1
    # not industry-clusterable
    assert "PROVISIONAL" not in CLUSTERABLE_TYPES
    clusters = feature_space_clusters(
        snap.entities, snap.observations, DEFAULT_CONFIG.clustering
    )
    cluster_ids = {eid for c in clusters for eid in c}
    assert prov.entity_id not in cluster_ids


@pytest.mark.unit
def test_row_level_stage_unresolved_and_custom_type():
    pkg = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [
            {
                "ref": "s1",
                "source_type": "PAPER",
                "publisher": "Journal",
                "title": "Paper",
                "published_at": "2019-01-01",
            }
        ],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "RESEARCH_ACTIVITY",
                "subject": "Dr Jane Q",
                "stage_unresolved": True,
                "subject_entity_type": "PERSON",
                "observed_at": "2019-01-01",
                "text_excerpt": "authored",
            }
        ],
    }
    snap = import_package(pkg)
    assert len(snap.observations) == 1
    person = next(e for e in snap.entities if e.canonical_name == "Dr Jane Q")
    assert person.entity_type == "PERSON"
    assert person.metadata.get("provisional") is True


@pytest.mark.unit
def test_provisional_reuse_same_name_across_observations():
    pkg = {
        "stage_unresolved_subjects": True,
        "entities": [],
        "sources": [
            {
                "ref": "s1",
                "source_type": "NEWS",
                "publisher": "Wire",
                "title": "A",
                "published_at": "2021-01-01",
            },
            {
                "ref": "s2",
                "source_type": "NEWS",
                "publisher": "Wire",
                "title": "B",
                "published_at": "2021-02-01",
            },
        ],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "PRODUCT_LAUNCH",
                "subject": "Mystery Corp",
                "observed_at": "2021-01-01",
                "text_excerpt": "launched",
            },
            {
                "source_ref": "s2",
                "observation_type": "HIRING_ACTIVITY",
                "subject": "Mystery Corp",
                "observed_at": "2021-02-01",
                "text_excerpt": "hiring",
            },
        ],
    }
    snap = import_package(pkg)
    assert len(snap.observations) == 2
    assert len([e for e in snap.entities if e.canonical_name == "Mystery Corp"]) == 1
    ids = {o.subject_entity for o in snap.observations}
    assert len(ids) == 1


@pytest.mark.unit
def test_ambiguous_name_not_staged():
    pkg = {
        "stage_unresolved": True,
        "entities": [
            {"entity_type": "COMPANY", "canonical_name": "Apex", "aliases": ["Delta"]},
            {"entity_type": "COMPANY", "canonical_name": "Beta", "aliases": ["Delta"]},
        ],
        "sources": [
            {
                "ref": "s1",
                "source_type": "NEWS",
                "publisher": "Wire",
                "title": "Note",
                "published_at": "2020-01-01",
            }
        ],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "HIRING_ACTIVITY",
                "subject": "Delta",
                "observed_at": "2020-01-01",
                "text_excerpt": "hiring",
            }
        ],
    }
    snap = import_package(pkg)
    assert snap.observations == []
    err = next(e for e in snap.import_errors if e.get("field") == "subject")
    assert "ambiguous" in (err.get("message") or "").lower()
    assert not any(e.canonical_name == "Delta" and e.entity_type == "PROVISIONAL" for e in snap.entities)


@pytest.mark.unit
def test_pure_ext_ref_failure_not_staged():
    pkg = {
        "stage_unresolved": True,
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [
            {
                "ref": "s1",
                "source_type": "NEWS",
                "publisher": "Wire",
                "title": "Note",
                "published_at": "2020-01-01",
            }
        ],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "STRATEGIC_INVESTMENT",
                "subject": "ext:lei:DOES-NOT-EXIST",
                "observed_at": "2020-01-01",
                "text_excerpt": "invested",
            }
        ],
    }
    snap = import_package(pkg)
    assert snap.observations == []
    assert snap.counts.get("provisional_entities", 0) == 0


@pytest.mark.unit
def test_object_staging_and_resolver_register():
    pkg = {
        "stage_unresolved": True,
        "provisional_entity_type": "PROVISIONAL",
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Buyer Co"}],
        "sources": [
            {
                "ref": "s1",
                "source_type": "COMPANY_FILING",
                "publisher": "SEC",
                "title": "8-K",
                "published_at": "2021-01-01",
            }
        ],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "SUPPLIER_RELATIONSHIP",
                "subject": "Buyer Co",
                "object": "New Supplier Inc",
                "observed_at": "2021-01-01",
                "text_excerpt": "supplies",
            }
        ],
    }
    snap = import_package(pkg)
    assert len(snap.observations) == 1
    obs = snap.observations[0]
    assert obs.metadata.get("object_provisional") is True
    supplier = next(e for e in snap.entities if e.canonical_name == "New Supplier Inc")
    assert supplier.entity_type == "PROVISIONAL"
    r = EntityResolver(snap.entities)
    assert r.resolve("New Supplier Inc") == supplier.entity_id


@pytest.mark.unit
def test_idempotent_reimport_with_provisional():
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
                "excerpt": "body",
            }
        ],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "HIRING_ACTIVITY",
                "subject": "Ephemeral LLC",
                "observed_at": "2020-01-01",
                "text_excerpt": "hiring engineers",
            }
        ],
    }
    a = import_package(pkg, created_at="2020-01-01T00:00:00+00:00")
    b = import_package(pkg, created_at="2020-01-01T00:00:00+00:00")
    assert a.snapshot_id == b.snapshot_id
    assert a.observations[0].subject_entity == b.observations[0].subject_entity

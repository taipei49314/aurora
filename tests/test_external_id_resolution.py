"""external_ids: ER resolve, merge-on-import, observation refs."""
from __future__ import annotations

import pytest

from aurora import import_package
from aurora.entity_resolution import EntityResolver, parse_entity_ref
from aurora.models import Entity


def _ent(eid, name, aliases=None, external_ids=None):
    return Entity(
        entity_id=eid,
        entity_type="COMPANY",
        canonical_name=name,
        aliases=aliases or [],
        external_ids=external_ids or [],
    )


@pytest.mark.unit
def test_resolve_by_ext_compact_string():
    r = EntityResolver([
        _ent("e1", "Acme Inc", external_ids=[{"system": "lei", "id": "LEI-ACME"}]),
    ])
    assert r.resolve("ext:lei:LEI-ACME") == "e1"
    assert r.resolve("lei:LEI-ACME") == "e1"


@pytest.mark.unit
def test_ambiguous_name_disambiguated_by_external_id():
    r = EntityResolver([
        _ent("e1", "Delta", external_ids=[{"system": "lei", "id": "L1"}]),
        _ent("e2", "Delta Holdings", aliases=["Delta"], external_ids=[{"system": "lei", "id": "L2"}]),
    ])
    assert r.resolve("Delta") is None  # still ambiguous without hint
    assert r.resolve("Delta", external_ids=[{"system": "lei", "id": "L2"}]) == "e2"


@pytest.mark.unit
def test_external_wins_over_stale_name():
    """Crosswalk: name points at old shell, external_id points at real company."""
    r = EntityResolver([
        _ent("e1", "Old Shell", aliases=["Trade Name"]),
        _ent("e2", "Real Co", external_ids=[{"system": "lei", "id": "REAL"}]),
    ])
    assert r.resolve("Trade Name", external_ids=[{"system": "lei", "id": "REAL"}]) == "e2"


@pytest.mark.unit
def test_parse_entity_ref_object():
    name, ext = parse_entity_ref({
        "name": "Acme",
        "external_ids": [{"system": "domain", "id": "acme.example"}],
    })
    assert name == "Acme"
    assert ext == [("domain", "acme.example")]


@pytest.mark.integration
def test_import_merges_entities_sharing_lei():
    pkg = {
        "entities": [
            {
                "entity_type": "COMPANY",
                "canonical_name": "FerroGrid Power",
                "external_ids": [{"system": "lei", "id": "LEI-FERRO"}],
            },
            {
                "entity_type": "COMPANY",
                "canonical_name": "Ferro Grid Power Inc.",
                "external_ids": [{"system": "lei", "id": "LEI-FERRO"}],
                "aliases": ["FG Power"],
            },
        ],
        "sources": [{
            "ref": "s1",
            "source_type": "NEWS",
            "publisher": "Wire",
            "title": "T",
            "excerpt": "E",
            "published_at": "2024-01-01",
        }],
        "observations": [{
            "source_ref": "s1",
            "observation_type": "PRODUCT_LAUNCH",
            "subject": "FG Power",
            "observed_at": "2024-01-01",
            "text_excerpt": "launch",
        }],
    }
    snap = import_package(pkg)
    companies = [e for e in snap.entities if e.entity_type == "COMPANY"]
    assert len(companies) == 1
    e = companies[0]
    assert e.canonical_name == "FerroGrid Power"
    assert "Ferro Grid Power Inc." in e.aliases
    assert "FG Power" in e.aliases
    assert any(x.get("id") == "LEI-FERRO" for x in e.external_ids)
    assert snap.import_errors == []
    assert len(snap.observations) == 1


@pytest.mark.integration
def test_import_obs_by_ext_ref_and_structured_subject():
    pkg = {
        "entities": [
            {
                "entity_type": "COMPANY",
                "canonical_name": "Acme",
                "external_ids": [{"system": "lei", "id": "L-ACME"}],
            },
            {
                "entity_type": "COMPANY",
                "canonical_name": "Beta",
                "external_ids": [{"system": "lei", "id": "L-BETA"}],
            },
        ],
        "sources": [{
            "ref": "s1",
            "source_type": "PATENT",
            "publisher": "USPTO",
            "title": "T",
            "excerpt": "E",
            "reliability_tier": "A",
            "published_at": "2020-01-01",
        }],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "PATENT_ACTIVITY",
                "subject": "ext:lei:L-ACME",
                "object": {
                    "name": "Someone",
                    "external_ids": [{"system": "lei", "id": "L-BETA"}],
                },
                "observed_at": "2020-01-01",
                "text_excerpt": "patent",
            }
        ],
    }
    snap = import_package(pkg)
    assert snap.import_errors == []
    assert len(snap.observations) == 1
    o = snap.observations[0]
    by_name = {e.entity_id: e.canonical_name for e in snap.entities}
    assert by_name[o.subject_entity] == "Acme"
    assert by_name[o.object_entity] == "Beta"


@pytest.mark.integration
def test_ambiguous_delta_resolved_with_subject_external_ids_field():
    pkg = {
        "entities": [
            {
                "entity_type": "COMPANY",
                "canonical_name": "Delta One",
                "aliases": ["Delta"],
                "external_ids": [{"system": "lei", "id": "D1"}],
            },
            {
                "entity_type": "COMPANY",
                "canonical_name": "Delta Two",
                "aliases": ["Delta"],
                "external_ids": [{"system": "lei", "id": "D2"}],
            },
        ],
        "sources": [{
            "ref": "s1",
            "source_type": "NEWS",
            "publisher": "W",
            "title": "T",
            "excerpt": "E",
            "published_at": "2021-01-01",
        }],
        "observations": [{
            "source_ref": "s1",
            "observation_type": "PRODUCT_LAUNCH",
            "subject": "Delta",
            "subject_external_ids": [{"system": "lei", "id": "D2"}],
            "observed_at": "2021-01-01",
            "text_excerpt": "x",
        }],
    }
    snap = import_package(pkg)
    # Shared alias "Delta" is still reported as a name ambiguity (informational),
    # but the observation resolves via subject_external_ids.
    assert len(snap.observations) == 1
    o = snap.observations[0]
    ent = next(e for e in snap.entities if e.entity_id == o.subject_entity)
    assert ent.canonical_name == "Delta Two"
    codes = {e.get("error_code") for e in snap.import_errors}
    assert "ENTITY_RESOLUTION_AMBIGUOUS" in codes

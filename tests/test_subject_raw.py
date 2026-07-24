"""First-class subject_raw / object_raw staging (engine 0.1.38+)."""
from __future__ import annotations

import pytest

from aurora import import_package
from aurora.ids import normalize_text


@pytest.mark.unit
def test_subject_raw_derived_from_name_and_preserved_on_alias():
    pkg = {
        "entities": [
            {
                "entity_type": "COMPANY",
                "canonical_name": "Monolith Corp",
                "aliases": ["Monolith Corporation"],
            }
        ],
        "sources": [
            {
                "ref": "s1",
                "source_type": "NEWS",
                "publisher": "Wire",
                "title": "Hire note",
                "published_at": "2020-01-01",
            }
        ],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "HIRING_ACTIVITY",
                "subject": "Monolith Corporation",
                "observed_at": "2020-01-01",
                "text_excerpt": "hiring",
            }
        ],
    }
    snap = import_package(pkg)
    assert len(snap.observations) == 1
    obs = snap.observations[0]
    assert obs.subject_raw == "Monolith Corporation"
    # resolved entity is the canonical id for Monolith Corp
    ent = next(e for e in snap.entities if e.canonical_name == "Monolith Corp")
    assert obs.subject_entity == ent.entity_id
    assert "subject_raw" not in (obs.metadata or {})


@pytest.mark.unit
def test_explicit_subject_raw_overrides_derivation():
    pkg = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [
            {
                "ref": "s1",
                "source_type": "NEWS",
                "publisher": "Wire",
                "title": "Note",
                "published_at": "2020-06-01",
            }
        ],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "PRODUCT_LAUNCH",
                "subject": "Acme",
                "subject_raw": "ACME, Inc. (as printed)",
                "observed_at": "2020-06-01",
                "text_excerpt": "launch",
            }
        ],
    }
    snap = import_package(pkg)
    obs = snap.observations[0]
    assert obs.subject_raw == "ACME, Inc. (as printed)"


@pytest.mark.unit
def test_subject_raw_only_resolves_when_name_matches():
    """Adapters may omit subject and pass subject_raw as the mention string."""
    pkg = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Beta Labs"}],
        "sources": [
            {
                "ref": "s1",
                "source_type": "PAPER",
                "publisher": "Journal",
                "title": "Paper",
                "published_at": "2019-03-01",
            }
        ],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "RESEARCH_ACTIVITY",
                "subject_raw": "Beta Labs",
                "observed_at": "2019-03-01",
                "text_excerpt": "study",
            }
        ],
    }
    snap = import_package(pkg)
    assert len(snap.observations) == 1
    obs = snap.observations[0]
    assert obs.subject_raw == "Beta Labs"
    ent = next(e for e in snap.entities if e.canonical_name == "Beta Labs")
    assert obs.subject_entity == ent.entity_id


@pytest.mark.unit
def test_object_raw_derived_and_metadata_fallback():
    pkg = {
        "entities": [
            {"entity_type": "COMPANY", "canonical_name": "Buyer Co"},
            {"entity_type": "COMPANY", "canonical_name": "Supplier Co", "aliases": ["SupCo"]},
        ],
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
                "object": "SupCo",
                "observed_at": "2021-01-01",
                "text_excerpt": "supplies",
                "metadata": {"object_raw": "SupCo LLC"},
            }
        ],
    }
    snap = import_package(pkg)
    obs = snap.observations[0]
    assert obs.subject_raw == "Buyer Co"
    # explicit metadata object_raw wins over derived "SupCo"
    assert obs.object_raw == "SupCo LLC"
    assert "object_raw" not in (obs.metadata or {})
    assert obs.object_entity is not None


@pytest.mark.unit
def test_unresolved_subject_raw_in_error_value():
    pkg = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Known"}],
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
                "subject": "Totally Unknown LLC",
                "observed_at": "2020-01-01",
                "text_excerpt": "hiring",
            }
        ],
    }
    snap = import_package(pkg)
    assert snap.observations == []
    codes = [e.get("error_code") for e in snap.import_errors]
    assert "ENTITY_RESOLUTION_AMBIGUOUS" in codes
    err = next(e for e in snap.import_errors if e.get("error_code") == "ENTITY_RESOLUTION_AMBIGUOUS")
    assert err.get("raw_value") == "Totally Unknown LLC"
    assert "subject_raw" in (err.get("message") or "")


@pytest.mark.unit
def test_ext_ref_subject_raw_from_explicit_or_compact():
    pkg = {
        "entities": [
            {
                "entity_type": "COMPANY",
                "canonical_name": "FerroGrid Power",
                "external_ids": [{"system": "lei", "id": "LEI-FERRO"}],
            }
        ],
        "sources": [
            {
                "ref": "s1",
                "source_type": "NEWS",
                "publisher": "Wire",
                "title": "Deal",
                "published_at": "2022-01-01",
            }
        ],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "STRATEGIC_INVESTMENT",
                "subject": "ext:lei:LEI-FERRO",
                "observed_at": "2022-01-01",
                "text_excerpt": "invested",
            },
            {
                "source_ref": "s1",
                "observation_type": "STRATEGIC_INVESTMENT",
                "subject": "ext:lei:LEI-FERRO",
                "subject_raw": "FerroGrid (trade print)",
                "observed_at": "2022-02-01",
                "text_excerpt": "followed on",
            },
        ],
    }
    snap = import_package(pkg)
    assert len(snap.observations) == 2
    by_excerpt = {o.text_excerpt: o for o in snap.observations}
    assert by_excerpt["invested"].subject_raw == "ext:lei:LEI-FERRO"
    assert by_excerpt["followed on"].subject_raw == "FerroGrid (trade print)"
    # both resolve to same entity
    assert by_excerpt["invested"].subject_entity == by_excerpt["followed on"].subject_entity


@pytest.mark.unit
def test_reimport_idempotent_with_subject_raw():
    pkg = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
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
                "subject": "Acme",
                "subject_raw": "Acme as printed",
                "observed_at": "2020-01-01",
                "text_excerpt": "hiring engineers",
            }
        ],
    }
    a = import_package(pkg, created_at="2020-01-01T00:00:00+00:00")
    b = import_package(pkg, created_at="2020-01-01T00:00:00+00:00")
    assert a.snapshot_id == b.snapshot_id
    assert a.observations[0].subject_raw == b.observations[0].subject_raw == "Acme as printed"
    # observation id is content-addressed without subject_raw (stable when raw changes)
    assert a.observations[0].observation_id == b.observations[0].observation_id
    # normalize_text still used for ids path
    assert normalize_text("Acme") == "acme"

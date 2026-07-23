"""First-class Entity.external_ids (import + SQL round-trip)."""
from __future__ import annotations

import pytest

from aurora import import_package


@pytest.mark.unit
def test_external_ids_first_class_and_metadata_fallback():
    pkg = {
        "entities": [
            {
                "entity_type": "COMPANY",
                "canonical_name": "Acme",
                "external_ids": [{"system": "lei", "id": "LEI1"}],
            },
            {
                "entity_type": "COMPANY",
                "canonical_name": "Beta",
                "metadata": {
                    "external_ids": [{"system": "domain", "id": "beta.example"}],
                    "note": "keep-me",
                },
            },
        ],
        "sources": [],
        "observations": [],
    }
    snap = import_package(pkg)
    by_name = {e.canonical_name: e for e in snap.entities}
    assert by_name["Acme"].external_ids == [{"system": "lei", "id": "LEI1"}]
    assert by_name["Beta"].external_ids == [{"system": "domain", "id": "beta.example"}]
    # lifted out of metadata so not duplicated
    assert "external_ids" not in by_name["Beta"].metadata
    assert by_name["Beta"].metadata.get("note") == "keep-me"


@pytest.mark.unit
def test_reimport_merges_external_ids():
    base = {
        "entities": [{
            "entity_type": "COMPANY",
            "canonical_name": "Acme",
            "external_ids": [{"system": "lei", "id": "LEI1"}],
        }],
        "sources": [],
        "observations": [],
    }
    # same package twice in one import already merges aliases; simulate second row
    pkg = {
        "entities": [
            {
                "entity_type": "COMPANY",
                "canonical_name": "Acme",
                "external_ids": [{"system": "lei", "id": "LEI1"}],
            },
            {
                "entity_type": "COMPANY",
                "canonical_name": "Acme",
                "external_ids": [{"system": "cik", "id": "0001"}],
            },
        ],
        "sources": [],
        "observations": [],
    }
    snap = import_package(pkg)
    acme = [e for e in snap.entities if e.canonical_name == "Acme"][0]
    systems = {x["system"] for x in acme.external_ids}
    assert systems == {"lei", "cik"}


@pytest.mark.integration
def test_sql_roundtrip_preserves_external_ids(tmp_path):
    from aurora.store_sql import make_engine, save_snapshot, load_snapshot

    pkg = {
        "entities": [{
            "entity_type": "COMPANY",
            "canonical_name": "Acme",
            "external_ids": [{"system": "lei", "id": "LEI9"}],
            "metadata": {"keep": 1},
        }],
        "sources": [],
        "observations": [],
    }
    snap = import_package(pkg)
    eng = make_engine(f"sqlite:///{tmp_path / 't.db'}")
    save_snapshot(eng, snap)
    loaded = load_snapshot(eng, snap.snapshot_id)
    e = loaded.entities[0]
    assert e.external_ids == [{"system": "lei", "id": "LEI9"}]
    assert e.metadata.get("keep") == 1
    assert "external_ids" not in e.metadata

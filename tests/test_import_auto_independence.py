"""Import auto-derives independence_group from wire/domain/family metadata."""
from __future__ import annotations

import pytest

from aurora import import_package


def _pkg(sources, observations=None):
    return {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": sources,
        "observations": observations or [],
    }


@pytest.mark.unit
def test_wire_id_metadata_groups_reprints():
    pkg = _pkg([
        {
            "ref": "a",
            "source_type": "NEWS",
            "publisher": "Wire",
            "title": "Same story",
            "excerpt": "body",
            "published_at": "2024-01-01",
            "metadata": {"wire_id": "reuters-x"},
        },
        {
            "ref": "b",
            "source_type": "NEWS",
            "publisher": "Local",
            "title": "Same story",
            "excerpt": "body",
            "published_at": "2024-01-01",
            "metadata": {"wire_id": "reuters-x"},
        },
    ], [
        {
            "source_ref": "a",
            "observation_type": "PRODUCT_LAUNCH",
            "subject": "Acme",
            "observed_at": "2024-01-01",
            "text_excerpt": "x",
        },
        {
            "source_ref": "b",
            "observation_type": "PRODUCT_LAUNCH",
            "subject": "Acme",
            "observed_at": "2024-01-01",
            "text_excerpt": "x",
        },
    ])
    snap = import_package(pkg)
    assert snap.import_errors == []
    groups = {s.independence_group for s in snap.sources}
    assert groups == {"wire:reuters-x"}
    assert all(s.wire_id == "reuters-x" for s in snap.sources)
    assert all("wire_id" not in (s.metadata or {}) for s in snap.sources)
    assert snap.counts["independent_source_count"] == 1
    assert snap.counts["raw_source_count"] == 2


@pytest.mark.unit
def test_top_level_outlet_domain_and_wire_id():
    """Engine 0.1.12+: outlet_domain / wire_id are first-class on Source."""
    pkg = _pkg([{
        "ref": "a",
        "source_type": "NEWS",
        "publisher": "Wire",
        "title": "Top-level outlet fields",
        "excerpt": "body",
        "published_at": "2024-03-01",
        "outlet_domain": "news.example",
        "wire_id": "wire-top",
    }])
    snap = import_package(pkg)
    src = snap.sources[0]
    assert src.outlet_domain == "news.example"
    assert src.wire_id == "wire-top"
    # wire wins over domain for independence
    assert src.independence_group == "wire:wire-top"
    assert "outlet_domain" not in (src.metadata or {})
    assert "wire_id" not in (src.metadata or {})


@pytest.mark.unit
def test_explicit_group_wins_over_metadata():
    pkg = _pkg([{
        "ref": "a",
        "source_type": "NEWS",
        "publisher": "Wire",
        "title": "T",
        "excerpt": "E",
        "independence_group": "manual:group",
        "metadata": {"wire_id": "ignored"},
    }])
    snap = import_package(pkg)
    assert snap.sources[0].independence_group == "manual:group"


@pytest.mark.unit
def test_outlet_domain_derives_domain_group():
    pkg = _pkg([{
        "ref": "a",
        "source_type": "NEWS",
        "publisher": "Chron",
        "title": "T",
        "excerpt": "E",
        "metadata": {"outlet_domain": "gridtech.example"},
    }])
    snap = import_package(pkg)
    assert snap.sources[0].independence_group == "domain:gridtech.example"
    assert snap.sources[0].outlet_domain == "gridtech.example"
    assert "outlet_domain" not in (snap.sources[0].metadata or {})


@pytest.mark.unit
def test_top_level_family_id_is_first_class():
    """Engine 0.1.8+: family_id on the source row is first-class, not only metadata."""
    pkg = _pkg([
        {
            "ref": "p1",
            "source_type": "PATENT",
            "publisher": "USPTO",
            "title": "Iron-air cell A",
            "excerpt": "abstract a",
            "published_at": "2020-01-01",
            "family_id": "fam-iron-1",
        },
        {
            "ref": "p2",
            "source_type": "PATENT",
            "publisher": "USPTO",
            "title": "Iron-air cell B",
            "excerpt": "abstract b",
            "published_at": "2021-01-01",
            "family_id": "fam-iron-1",
        },
    ], [
        {
            "source_ref": "p1",
            "observation_type": "PATENT_ACTIVITY",
            "subject": "Acme",
            "observed_at": "2020-01-01",
            "text_excerpt": "a",
        },
        {
            "source_ref": "p2",
            "observation_type": "PATENT_ACTIVITY",
            "subject": "Acme",
            "observed_at": "2021-01-01",
            "text_excerpt": "b",
        },
    ])
    snap = import_package(pkg)
    assert snap.import_errors == []
    assert all(s.family_id == "fam-iron-1" for s in snap.sources)
    assert {s.independence_group for s in snap.sources} == {"family:fam-iron-1"}
    assert snap.counts["independent_source_count"] == 1
    assert snap.counts["raw_source_count"] == 2
    # promoted out of metadata when only top-level was provided
    assert all("family_id" not in (s.metadata or {}) for s in snap.sources)


@pytest.mark.unit
def test_metadata_family_id_promoted_to_field():
    pkg = _pkg([{
        "ref": "a",
        "source_type": "PATENT",
        "publisher": "USPTO",
        "title": "T",
        "excerpt": "E",
        "metadata": {"family_id": "fam-meta-9"},
    }])
    snap = import_package(pkg)
    src = snap.sources[0]
    assert src.family_id == "fam-meta-9"
    assert src.independence_group == "family:fam-meta-9"
    assert "family_id" not in (src.metadata or {})


@pytest.mark.unit
def test_top_level_event_date_is_first_class():
    """Engine 0.1.10+: event_date (app/filing) vs published_at (grant/pub)."""
    pkg = _pkg([{
        "ref": "p1",
        "source_type": "PATENT",
        "publisher": "USPTO",
        "title": "Dual date patent",
        "excerpt": "body",
        "published_at": "2022-04-12",
        "event_date": "2021-11-02",
    }], [{
        "source_ref": "p1",
        "observation_type": "PATENT_ACTIVITY",
        "subject": "Acme",
        "observed_at": "2021-11-02",
        "text_excerpt": "filed",
    }])
    snap = import_package(pkg)
    assert snap.import_errors == []
    src = snap.sources[0]
    assert src.event_date == "2021-11-02"
    assert src.published_at == "2022-04-12"
    assert "event_date" not in (src.metadata or {})


@pytest.mark.unit
def test_metadata_event_date_promoted_and_observed_at_fallback():
    """Metadata event_date promoted; missing observed_at falls back to event_date."""
    pkg = _pkg([{
        "ref": "p1",
        "source_type": "PATENT",
        "publisher": "USPTO",
        "title": "Fallback date patent",
        "excerpt": "body",
        "published_at": "2023-01-15",
        "metadata": {"event_date": "2020-06-01"},
    }], [{
        "source_ref": "p1",
        "observation_type": "PATENT_ACTIVITY",
        "subject": "Acme",
        # no observed_at → engine uses source.event_date
        "text_excerpt": "filed",
    }])
    snap = import_package(pkg)
    assert snap.import_errors == []
    src = snap.sources[0]
    assert src.event_date == "2020-06-01"
    assert "event_date" not in (src.metadata or {})
    assert len(snap.observations) == 1
    assert snap.observations[0].observed_at == "2020-06-01"


@pytest.mark.unit
def test_event_id_first_class_and_source_independence():
    """Engine 0.1.11+: event_id on sources collapses independence; obs inherits."""
    pkg = _pkg([
        {
            "ref": "a",
            "source_type": "NEWS",
            "publisher": "Wire A",
            "title": "Supply deal",
            "excerpt": "body a",
            "published_at": "2024-01-01",
            "event_id": "evt_supply_2024",
        },
        {
            "ref": "b",
            "source_type": "NEWS",
            "publisher": "Wire B",
            "title": "Different headline same deal",
            "excerpt": "body b different",
            "published_at": "2024-01-02",
            "event_id": "evt_supply_2024",
        },
    ], [
        {
            "source_ref": "a",
            "observation_type": "SUPPLIER_RELATIONSHIP",
            "subject": "Acme",
            "observed_at": "2024-01-01",
            "text_excerpt": "deal a",
            # no event_id → inherit from source
        },
        {
            "source_ref": "b",
            "observation_type": "SUPPLIER_RELATIONSHIP",
            "subject": "Acme",
            "observed_at": "2024-01-02",
            "text_excerpt": "deal b",
            "event_id": "evt_supply_2024",
        },
    ])
    snap = import_package(pkg)
    assert snap.import_errors == []
    assert all(s.event_id == "evt_supply_2024" for s in snap.sources)
    # empty independence_group derives event:… OR dedup layer 2b merges
    assert snap.counts["independent_source_count"] == 1
    assert snap.counts["raw_source_count"] == 2
    assert all(o.event_id == "evt_supply_2024" for o in snap.observations)

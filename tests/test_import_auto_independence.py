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
    assert snap.counts["independent_source_count"] == 1
    assert snap.counts["raw_source_count"] == 2


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

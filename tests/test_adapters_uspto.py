"""USPTO offline adapter -> import package contract tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import convert_uspto, merge_packages, strip_package  # noqa: E402
from adapters.package_util import package_stats  # noqa: E402
from aurora import import_package  # noqa: E402

FIXTURE = ROOT / "adapters" / "fixtures" / "uspto_sample.json"


@pytest.fixture(scope="module")
def uspto_raw():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def uspto_pkg(uspto_raw):
    return convert_uspto(uspto_raw)


@pytest.mark.unit
def test_convert_counts_and_refs(uspto_pkg, uspto_raw):
    stats = package_stats(uspto_pkg)
    assert stats["sources"] == len(uspto_raw["patents"])
    assert stats["orphan_observations"] == 0
    assert stats["observations"] >= stats["sources"]
    # assignees include FerroGrid, OxaCell, LongHaul + tech/component/material
    names = {e["canonical_name"] for e in uspto_pkg["entities"]}
    assert "FerroGrid Power" in names
    assert "OxaCell Systems" in names
    assert "LongHaul Energy" in names
    assert "reversible iron oxidation" in names


@pytest.mark.unit
def test_date_policy_application_vs_publication(uspto_pkg):
    by_ref = {s["ref"]: s for s in uspto_pkg["sources"]}
    src = by_ref["pat-us20220123456a1"]
    assert src["published_at"] == "2022-04-12"
    assert src["metadata"]["event_date"] == "2021-11-02"
    obs = [o for o in uspto_pkg["observations"] if o["source_ref"] == src["ref"]]
    assert obs
    assert all(o["observed_at"] == "2021-11-02" for o in obs)


@pytest.mark.unit
def test_family_independence_group(uspto_pkg):
    groups = {
        s["independence_group"]
        for s in uspto_pkg["sources"]
        if "ironair-ferro" in s.get("independence_group", "")
    }
    assert groups == {"family:ironair-ferro-2022"}
    # two Ferro family patents share group
    ferro_family = [
        s for s in uspto_pkg["sources"]
        if s["independence_group"] == "family:ironair-ferro-2022"
    ]
    assert len(ferro_family) == 2


@pytest.mark.unit
def test_merge_packages_dedupes_entities(uspto_pkg):
    other = {
        "entities": [
            {
                "entity_type": "COMPANY",
                "canonical_name": "FerroGrid Power",
                "aliases": ["FerroGrid"],
                "metadata": {
                    "external_ids": [{"system": "lei", "id": "549300TEST"}]
                },
            }
        ],
        "sources": [],
        "observations": [],
    }
    merged = merge_packages([uspto_pkg, other])
    ferro = [
        e for e in merged["entities"] if e["canonical_name"] == "FerroGrid Power"
    ]
    assert len(ferro) == 1
    assert "FerroGrid" in ferro[0]["aliases"]
    ids = ferro[0]["metadata"]["external_ids"]
    systems = {x["system"] for x in ids}
    assert "lei" in systems
    assert "uspto_assignee_name" in systems


@pytest.mark.integration
def test_uspto_package_imports_clean(uspto_pkg):
    snap = import_package(strip_package(uspto_pkg))
    assert snap.import_errors == []
    assert len(snap.sources) == 3
    # family share → independent sources < raw
    assert snap.counts["independent_source_count"] < snap.counts["raw_source_count"]
    assert snap.counts["raw_source_count"] == 3
    assert snap.counts["independent_source_count"] == 2


@pytest.mark.integration
def test_uspto_package_pipeline_runs(uspto_pkg):
    from aurora import DEFAULT_CONFIG, Taxonomy, run_pipeline

    snap = import_package(strip_package(uspto_pkg))
    tax = Taxonomy.load(ROOT / "datasets" / "taxonomy" / "taxonomy.json")
    run = run_pipeline(snap, tax, DEFAULT_CONFIG, cutoff_date=None)
    assert run.run_id
    # small patent-only package may not form a full INDUSTRY_CANDIDATE;
    # require deterministic completion only
    assert isinstance(run.hypotheses, list)


@pytest.mark.unit
def test_missing_patents_key_raises():
    with pytest.raises(ValueError, match="patents"):
        convert_uspto({})


@pytest.mark.unit
def test_missing_publication_number_raises():
    with pytest.raises(ValueError, match="publication_number"):
        convert_uspto({"patents": [{"title": "x"}]})

"""PatentsView-compatible offline adapter tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import convert_patentsview, strip_package  # noqa: E402
from adapters.package_util import package_stats  # noqa: E402
from adapters.patentsview import normalize_patentsview_record  # noqa: E402
from aurora import import_package  # noqa: E402
from aurora import leakage as leakage_mod  # noqa: E402
from aurora import DEFAULT_CONFIG, Taxonomy, run_pipeline  # noqa: E402

FIX = ROOT / "adapters" / "fixtures" / "patentsview_sample.json"


@pytest.fixture(scope="module")
def pv_raw():
    return json.loads(FIX.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pv_pkg(pv_raw):
    return convert_patentsview(pv_raw)


@pytest.mark.unit
def test_normalize_patentsview_fields():
    rec = normalize_patentsview_record({
        "patent_number": "123",
        "patent_title": "T",
        "patent_abstract": "A",
        "patent_date": "2020-01-02",
        "app_date": "2019-01-01",
        "assignee_organization": "Acme Co",
        "assignee_country": "US",
        "cpcs": [{"cpc_subgroup_id": "H01M4/86"}],
    })
    assert rec["publication_number"] == "123"
    assert rec["assignees"][0]["name"] == "Acme Co"
    assert "H01M4/86" in rec["cpc"]


@pytest.mark.unit
def test_patentsview_counts_and_family(pv_pkg, pv_raw):
    stats = package_stats(pv_pkg)
    assert stats["sources"] == len(pv_raw["patents"])
    assert stats["orphan_observations"] == 0
    families = {s["independence_group"] for s in pv_pkg["sources"]}
    assert "family:fam-ironair-2018" in families
    # two patents share fam-ironair-2018
    shared = [
        s for s in pv_pkg["sources"]
        if s["independence_group"] == "family:fam-ironair-2018"
    ]
    assert len(shared) == 2
    assert pv_pkg["_adapter"]["id"] == "patentsview-offline"


@pytest.mark.integration
def test_patentsview_imports_and_independence(pv_pkg):
    snap = import_package(strip_package(pv_pkg))
    assert snap.import_errors == []
    assert snap.counts["raw_source_count"] == 4
    assert snap.counts["independent_source_count"] == 3  # one family share


@pytest.mark.integration
def test_patentsview_cutoff_leakage_zero(pv_pkg):
    snap = import_package(strip_package(pv_pkg))
    cut = leakage_mod.apply_cutoff(snap.observations, snap.sources, "2020-12-31")
    leakage_mod.assert_no_leakage(cut["observations"], "2020-12-31")
    assert cut["manifest"]["excluded_future_observation_count"] > 0
    assert cut["manifest"]["included_observation_count"] > 0
    # early run must complete
    tax = Taxonomy.load(ROOT / "datasets" / "taxonomy" / "taxonomy.json")
    run = run_pipeline(snap, tax, DEFAULT_CONFIG, cutoff_date="2020-12-31")
    assert run.run_id


@pytest.mark.unit
def test_missing_patents_raises():
    with pytest.raises(ValueError, match="patents"):
        convert_patentsview({})


@pytest.mark.unit
def test_patentsview_inventors_are_person_entities(pv_pkg):
    people = [e for e in pv_pkg["entities"] if e.get("entity_type") == "PERSON"]
    assert people, "expected at least one PERSON from patentsview inventors fixture"
    assert any("Researcher" in e.get("canonical_name", "") for e in people)

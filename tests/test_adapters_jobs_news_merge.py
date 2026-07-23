"""Jobs + news adapters and multi-package merge."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import (  # noqa: E402
    convert_jobs,
    convert_news,
    convert_uspto,
    merge_packages,
    strip_package,
)
from adapters.package_util import package_stats  # noqa: E402
from aurora import import_package  # noqa: E402

FIX = ROOT / "adapters" / "fixtures"


@pytest.fixture(scope="module")
def jobs_pkg():
    raw = json.loads((FIX / "jobs_sample.json").read_text(encoding="utf-8"))
    return convert_jobs(raw)


@pytest.fixture(scope="module")
def news_pkg():
    raw = json.loads((FIX / "news_sample.json").read_text(encoding="utf-8"))
    return convert_news(raw)


@pytest.fixture(scope="module")
def uspto_pkg():
    raw = json.loads((FIX / "uspto_sample.json").read_text(encoding="utf-8"))
    return convert_uspto(raw)


@pytest.mark.unit
def test_jobs_emits_hiring(jobs_pkg):
    stats = package_stats(jobs_pkg)
    assert stats["orphan_observations"] == 0
    assert stats["sources"] == 3
    types = {o["observation_type"] for o in jobs_pkg["observations"]}
    assert "HIRING_ACTIVITY" in types
    hiring = [
        o for o in jobs_pkg["observations"] if o["observation_type"] == "HIRING_ACTIVITY"
    ]
    assert any(o.get("unit") == "openings" for o in hiring)
    assert any(o["subject"] == "FerroGrid Power" for o in hiring)


@pytest.mark.integration
def test_jobs_imports_clean(jobs_pkg):
    snap = import_package(strip_package(jobs_pkg))
    assert snap.import_errors == []
    assert snap.counts["raw_source_count"] == 3


@pytest.mark.unit
def test_news_reprint_shares_wire_group(news_pkg):
    by_id = {s["ref"]: s for s in news_pkg["sources"]}
    primary = by_id["news-reuter-ferro-supply-2024"]
    reprint = by_id["news-regional-reprint-supply-2024"]
    assert primary["independence_group"] == "wire:example-reuter"
    assert reprint["independence_group"] == "wire:example-reuter"
    assert reprint["reliability_tier"] == "D"
    types = {o["observation_type"] for o in news_pkg["observations"]}
    assert "SUPPLIER_RELATIONSHIP" in types
    assert "ADOPTION_SIGNAL" in types


@pytest.mark.integration
def test_news_imports_and_independence_not_inflated(news_pkg):
    snap = import_package(strip_package(news_pkg))
    assert snap.import_errors == []
    # 3 articles, but wire primary+reprint share independence → independent < raw
    assert snap.counts["raw_source_count"] == 3
    assert snap.counts["independent_source_count"] == 2


@pytest.mark.integration
def test_merge_uspto_jobs_news(uspto_pkg, jobs_pkg, news_pkg):
    merged = merge_packages([uspto_pkg, jobs_pkg, news_pkg])
    stats = package_stats(merged)
    assert stats["orphan_observations"] == 0
    assert stats["sources"] == 3 + 3 + 3  # patents + jobs + news
    # FerroGrid entity merged once
    ferro = [
        e for e in merged["entities"] if e["canonical_name"] == "FerroGrid Power"
    ]
    assert len(ferro) == 1

    snap = import_package(strip_package(merged))
    assert snap.import_errors == []
    assert snap.counts["raw_source_count"] == 9
    # family (2 patents share) + wire reprint (2 news share) → at most 7 independent
    assert snap.counts["independent_source_count"] <= 7
    assert snap.counts["independent_source_count"] < snap.counts["raw_source_count"]

    obs_types = {o.observation_type for o in snap.observations}
    assert "PATENT_ACTIVITY" in obs_types
    assert "HIRING_ACTIVITY" in obs_types
    assert "SUPPLIER_RELATIONSHIP" in obs_types


@pytest.mark.integration
def test_merge_pipeline_runs(uspto_pkg, jobs_pkg, news_pkg):
    from aurora import DEFAULT_CONFIG, Taxonomy, run_pipeline

    merged = merge_packages([uspto_pkg, jobs_pkg, news_pkg])
    snap = import_package(strip_package(merged))
    tax = Taxonomy.load(ROOT / "datasets" / "taxonomy" / "taxonomy.json")
    run = run_pipeline(snap, tax, DEFAULT_CONFIG, cutoff_date=None)
    assert run.run_id
    assert isinstance(run.hypotheses, list)


@pytest.mark.unit
def test_jobs_missing_postings_raises():
    with pytest.raises(ValueError, match="postings"):
        convert_jobs({})


@pytest.mark.unit
def test_news_missing_articles_raises():
    with pytest.raises(ValueError, match="articles"):
        convert_news({})

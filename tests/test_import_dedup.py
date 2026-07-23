"""Import pipeline, deduplication, source independence, re-import idempotency."""
from __future__ import annotations

import pytest as _pytest
pytestmark = _pytest.mark.unit

from aurora import import_package
from aurora.dedup import resolve_independence, jaccard


def test_import_produces_entities_sources_observations(snapshot):
    assert snapshot.counts["entities"] > 40
    assert snapshot.counts["observations"] > 300
    assert snapshot.counts["sources"] > 300


def test_reimport_is_idempotent(package):
    a = import_package(package)
    b = import_package(package)
    assert a.snapshot_id == b.snapshot_id
    assert a.counts["observations"] == b.counts["observations"]
    # importing twice must NOT double the evidence
    assert a.counts["observations"] == b.counts["observations"] < 2 * a.counts["observations"] + 1


def test_independent_less_than_raw_when_reprints_exist(snapshot):
    raw = snapshot.counts["raw_source_count"]
    indep = snapshot.counts["independent_source_count"]
    assert indep < raw, "syndicated reprints must reduce independent source count"


def test_exact_duplicate_sources_collapse():
    pkg = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [
            {"ref": "a", "source_type": "NEWS", "publisher": "P", "title": "T", "excerpt": "same body",
             "published_at": "2022-01-01"},
            {"ref": "b", "source_type": "NEWS", "publisher": "P", "title": "T", "excerpt": "same body",
             "published_at": "2022-01-01"},
        ],
        "observations": [
            {"ref": "o", "source_ref": "a", "observation_type": "PRODUCT_LAUNCH", "subject": "Acme"},
            {"source_ref": "b", "observation_type": "PRODUCT_LAUNCH", "subject": "Acme"},
        ],
    }
    snap = import_package(pkg)
    # identical content hash -> one deduplicated source
    assert snap.counts["deduplicated_source_count"] == 1


def test_declared_independence_group_merges():
    class S:
        def __init__(self, sid, chash, grp, title):
            self.source_id, self.content_hash, self.independence_group = sid, chash, grp
            self.title, self.metadata = title, {}
    srcs = [S("s1", "h1", "wire", "a"), S("s2", "h2", "wire", "b"), S("s3", "h3", "", "c")]
    res = resolve_independence(srcs)
    assert res["independent_source_count"] == 2  # wire group collapses s1,s2


def test_near_duplicate_detection():
    a = set("the quick brown fox jumps".split())
    b = set("the quick brown fox jumped".split())
    assert jaccard(a, b) > 0.5


def test_missing_date_is_flagged_not_dropped(snapshot):
    undated = [o for o in snapshot.observations if not o.observed_at]
    assert len(undated) >= 1  # the noise observation with missing date survives import


def test_schema_error_reported_with_context():
    pkg = {"entities": [{"entity_type": "NOT_A_TYPE", "canonical_name": "X"}],
           "sources": [], "observations": []}
    snap = import_package(pkg)
    codes = {e["error_code"] for e in snap.import_errors}
    assert "SCHEMA_VALIDATION_FAILED" in codes


def test_unknown_source_ref_reported():
    pkg = {"entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}], "sources": [],
           "observations": [{"source_ref": "ghost", "observation_type": "PRODUCT_LAUNCH", "subject": "Acme"}]}
    snap = import_package(pkg)
    assert any(e["field"] == "source_ref" for e in snap.import_errors)

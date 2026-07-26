"""Import pipeline, deduplication, source independence, re-import idempotency."""
from __future__ import annotations

import copy

import pytest as _pytest
pytestmark = _pytest.mark.unit

from aurora import import_package
from aurora.dedup import resolve_independence, jaccard


def _manifest_fixture() -> dict:
    return {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [{
            "ref": "s1", "source_type": "NEWS", "publisher": "Wire",
            "title": "Acme activity", "published_at": "2024-01-01",
            "excerpt": "Acme hired engineers.",
        }],
        "observations": [{
            "source_ref": "s1", "observation_type": "HIRING_ACTIVITY",
            "subject": "Acme", "observed_at": "2024-01-01",
            "numeric_value": 12, "confidence": 0.8,
            "text_excerpt": "hired engineers",
        }],
    }


def test_input_manifest_hash_covers_observation_content_and_is_deterministic():
    package = _manifest_fixture()
    baseline = import_package(package, created_at="2024-01-02T00:00:00+00:00")
    identical = import_package(copy.deepcopy(package), created_at="2024-01-02T00:00:00+00:00")

    assert baseline.input_manifest_hash().startswith("v2:")
    assert baseline.input_manifest_hash() == identical.input_manifest_hash()

    confidence_changed = copy.deepcopy(package)
    confidence_changed["observations"][0]["confidence"] = 0.01
    confidence_snapshot = import_package(
        confidence_changed, created_at="2024-01-02T00:00:00+00:00"
    )
    assert baseline.input_manifest_hash() != confidence_snapshot.input_manifest_hash()
    assert baseline.observations[0].observation_id == confidence_snapshot.observations[0].observation_id

    numeric_value_changed = copy.deepcopy(package)
    numeric_value_changed["observations"][0]["numeric_value"] = 13
    numeric_snapshot = import_package(
        numeric_value_changed, created_at="2024-01-02T00:00:00+00:00"
    )
    assert baseline.input_manifest_hash() != numeric_snapshot.input_manifest_hash()
    assert baseline.observations[0].observation_id == numeric_snapshot.observations[0].observation_id


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
        def __init__(self, sid, chash, grp, title, event_id=""):
            self.source_id, self.content_hash, self.independence_group = sid, chash, grp
            self.title, self.metadata = title, {}
            self.event_id = event_id
    srcs = [S("s1", "h1", "wire", "a"), S("s2", "h2", "wire", "b"), S("s3", "h3", "", "c")]
    res = resolve_independence(srcs)
    assert res["independent_source_count"] == 2  # wire group collapses s1,s2


def test_shared_event_id_merges_independence():
    """Sources with the same event_id collapse even when independence_group differs."""
    class S:
        def __init__(self, sid, chash, grp, title, event_id=""):
            self.source_id, self.content_hash, self.independence_group = sid, chash, grp
            self.title, self.metadata = title, {}
            self.event_id = event_id
    # Distinct multi-token titles so near-dup LSH does not merge unrelated events
    srcs = [
        S("s1", "h1", "wire:a", "ferrogrid signs purechitin supply deal", event_id="evt_supply"),
        S("s2", "h2", "wire:b", "regional daily covers powder feedstock pact", event_id="evt_supply"),
        S("s3", "h3", "wire:c", "longhaul pilots hundred hour iron air modules", event_id="evt_other"),
    ]
    res = resolve_independence(srcs)
    assert res["independent_source_count"] == 2
    assert res["resolved_group"]["s1"] == res["resolved_group"]["s2"]
    assert res["resolved_group"]["s3"] != res["resolved_group"]["s1"]


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

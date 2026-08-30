"""Temporal cutoff, future-leakage prevention, historical backtest."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest as _pytest
pytestmark = _pytest.mark.integration

import pytest

from aurora import import_package, run_pipeline, DEFAULT_CONFIG
from aurora import leakage
from aurora.backtest import (
    BACKTEST_MANIFEST_SCHEMA,
    backtest_identity,
    backtest_manifest_sha256,
    run_backtest,
)
from aurora.errors import AuroraError


def test_cutoff_excludes_future_observations(snapshot):
    cut = leakage.apply_cutoff(snapshot.observations, snapshot.sources, "2021-12-31")
    assert cut["manifest"]["excluded_future_observation_count"] > 0
    for o in cut["observations"]:
        assert o.observed_at is None or o.observed_at <= "2021-12-31"


def test_no_leakage_assertion_passes_on_clean_subset(snapshot):
    cut = leakage.apply_cutoff(snapshot.observations, snapshot.sources, "2022-06-30")
    leakage.assert_no_leakage(cut["observations"], cut["sources"], "2022-06-30")  # must not raise


def test_leakage_detected_when_future_slips_in(snapshot):
    future = [o for o in snapshot.observations if o.observed_at and o.observed_at > "2021-12-31"][:1]
    with pytest.raises(AuroraError) as exc:
        leakage.assert_no_leakage(future, snapshot.sources, "2021-12-31")
    assert exc.value.error_code == "FUTURE_DATA_LEAKAGE"


def test_invalid_cutoff_raises():
    with pytest.raises(AuroraError) as exc:
        leakage.parse_cutoff("not-a-date")
    assert exc.value.error_code == "INVALID_CUTOFF_DATE"


def test_cutoff_run_has_fewer_or_equal_candidates(snapshot, taxonomy):
    early = run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG, cutoff_date="2021-12-31")
    full = run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG, cutoff_date=None)
    n_early = sum(1 for h in early.hypotheses if h.status == "INDUSTRY_CANDIDATE")
    n_full = sum(1 for h in full.hypotheses if h.status == "INDUSTRY_CANDIDATE")
    assert n_early <= n_full


def test_pipeline_anchors_hype_windows_at_cutoff(snapshot, taxonomy, monkeypatch):
    import aurora.pipeline as pipeline_module

    real_assessment = pipeline_module.hype_assessment
    seen_as_of = []

    def capture_assessment(cluster, observations, *, as_of=None):
        seen_as_of.append(as_of)
        return real_assessment(cluster, observations, as_of=as_of)

    monkeypatch.setattr(pipeline_module, "hype_assessment", capture_assessment)
    run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG, cutoff_date="2021-12-31")

    assert seen_as_of
    assert set(seen_as_of) == {"2021-12-31"}


def test_backtest_reports_no_leakage_and_tracks(snapshot, taxonomy):
    bt = run_backtest(snapshot, taxonomy, ["2020-12-31", "2022-12-31", "2024-12-31"], DEFAULT_CONFIG)
    assert bt["future_leakage_violations"] == 0
    assert bt["tracks"]
    # hype/failed clusters must not be reported as early industry candidates
    assert bt["false_positive_candidates"] == [] or all(
        "quantum" not in n and "metaverse" not in n for n in bt["false_positive_candidates"])


def test_backtest_detects_industries_before_full_run(snapshot, taxonomy):
    bt = run_backtest(snapshot, taxonomy, ["2021-12-31", "2023-12-31", "2025-06-30"], DEFAULT_CONFIG)
    emerging_tracks = [t for t in bt["tracks"]
                       if t["final_status"] == "INDUSTRY_CANDIDATE" and t["first_emerging_cutoff"]]
    assert emerging_tracks, "at least one real industry should be detectable before the last cutoff"


def test_backtest_audit_manifest_is_deterministic(fast_snapshot, taxonomy):
    cutoffs = ["2022-12-31", "2020-12-31"]
    first = run_backtest(fast_snapshot, taxonomy, cutoffs, DEFAULT_CONFIG)
    replay = run_backtest(fast_snapshot, taxonomy, cutoffs, DEFAULT_CONFIG)

    # Existing compact consumers remain valid; audit fields are additive.
    assert {
        "cutoffs",
        "tracks",
        "median_early_discovery_lead_days",
        "false_positive_candidates",
        "future_leakage_violations",
    } <= first.keys()
    assert first["backtest_manifest"] == replay["backtest_manifest"]
    assert first["backtest_manifest_hash"] == replay["backtest_manifest_hash"]
    assert first["backtest_identity"] == replay["backtest_identity"]

    manifest = first["backtest_manifest"]
    assert manifest["schema_version"] == BACKTEST_MANIFEST_SCHEMA
    assert manifest["snapshot_id"] == fast_snapshot.snapshot_id
    assert manifest["input_manifest_hash"] == fast_snapshot.input_manifest_hash()
    assert manifest["config_manifest"] == DEFAULT_CONFIG.manifest()
    assert manifest["config_manifest_hash"].startswith("sha256:")
    assert manifest["versions"] == {
        "engine_version": DEFAULT_CONFIG.engine_version,
        "feature_version": DEFAULT_CONFIG.feature_version,
        "taxonomy_version": DEFAULT_CONFIG.taxonomy_version,
    }
    assert manifest["cutoffs"] == sorted(cutoffs)
    assert [run["cutoff"] for run in manifest["cutoff_runs"]] == sorted(cutoffs)
    assert manifest["full_run"]["cutoff"] is None
    for run in [*manifest["cutoff_runs"], manifest["full_run"]]:
        assert run["run_id"].startswith("run_")
        assert run["input_manifest_hash"] == manifest["input_manifest_hash"]
        assert run["result_manifest_hash"]
        assert isinstance(run["leakage_manifest"], dict)

    assert first["backtest_manifest_hash"] == backtest_manifest_sha256(manifest)
    assert first["backtest_identity"] == backtest_identity(manifest)


def test_backtest_identity_changes_with_config(fast_snapshot, taxonomy):
    changed_cfg = replace(
        DEFAULT_CONFIG,
        classification=replace(
            DEFAULT_CONFIG.classification,
            candidate_min_overall=DEFAULT_CONFIG.classification.candidate_min_overall + 1,
        ),
    )
    baseline = run_backtest(
        fast_snapshot, taxonomy, ["2022-12-31"], DEFAULT_CONFIG
    )
    changed = run_backtest(
        fast_snapshot, taxonomy, ["2022-12-31"], changed_cfg
    )

    assert (
        baseline["backtest_manifest"]["input_manifest_hash"]
        == changed["backtest_manifest"]["input_manifest_hash"]
    )
    assert (
        baseline["backtest_manifest"]["config_manifest_hash"]
        != changed["backtest_manifest"]["config_manifest_hash"]
    )
    assert baseline["backtest_manifest_hash"] != changed["backtest_manifest_hash"]
    assert baseline["backtest_identity"] != changed["backtest_identity"]


def _snapshot_with_corpus_lineage(snapshot, digest_character):
    changed = deepcopy(snapshot)
    source = changed.sources[0]
    source.metadata = dict(source.metadata or {})
    source.metadata["corpus_lineage"] = {
        "schema_version": "aurora-package-lineage/v1",
        "datasets": [
            {
                "schema_version": "aurora-corpus-lineage/v1",
                "dataset_id": "audit-fixture",
                "dataset_version": "2026-08",
                "artifact_sha256": "sha256:" + digest_character * 64,
                "manifest_sha256": "sha256:" + digest_character * 64,
                "origin_url": "https://example.invalid/mutable-location",
                "license": "example license prose is intentionally not copied",
            }
        ],
    }
    return changed


def test_backtest_identity_changes_with_corpus_lineage(fast_snapshot, taxonomy):
    corpus_a = _snapshot_with_corpus_lineage(fast_snapshot, "a")
    corpus_b = _snapshot_with_corpus_lineage(fast_snapshot, "b")
    first = run_backtest(corpus_a, taxonomy, ["2022-12-31"], DEFAULT_CONFIG)
    changed = run_backtest(corpus_b, taxonomy, ["2022-12-31"], DEFAULT_CONFIG)

    first_manifest = first["backtest_manifest"]
    changed_manifest = changed["backtest_manifest"]
    assert first_manifest["snapshot_id"] == changed_manifest["snapshot_id"]
    assert first_manifest["input_manifest_hash"] != changed_manifest["input_manifest_hash"]
    assert first_manifest["corpus_lineage_refs"] != changed_manifest["corpus_lineage_refs"]
    assert first["backtest_manifest_hash"] != changed["backtest_manifest_hash"]
    assert first["backtest_identity"] != changed["backtest_identity"]

    assert first_manifest["corpus_lineage_refs"] == [{
        "schema_version": "aurora-corpus-lineage/v1",
        "dataset_id": "audit-fixture",
        "dataset_version": "2026-08",
        "artifact_sha256": "sha256:" + "a" * 64,
        "manifest_sha256": "sha256:" + "a" * 64,
    }]


def test_backtest_manifest_keeps_lineage_from_source_provenance_aliases(
    fast_snapshot, taxonomy
):
    snapshot = _snapshot_with_corpus_lineage(fast_snapshot, "a")
    snapshot.sources[0].metadata["provenance_aliases"] = [
        {
            "metadata": {
                "corpus_lineage": {
                    "schema_version": "aurora-corpus-lineage/v1",
                    "dataset_id": "second-corpus",
                    "dataset_version": "2026-09",
                    "artifact_sha256": "sha256:" + "b" * 64,
                    "manifest_sha256": "sha256:" + "c" * 64,
                }
            }
        }
    ]

    result = run_backtest(
        snapshot, taxonomy, ["2022-12-31"], DEFAULT_CONFIG
    )
    references = result["backtest_manifest"]["corpus_lineage_refs"]

    assert {reference["dataset_id"] for reference in references} == {
        "audit-fixture",
        "second-corpus",
    }


def test_package_level_lineage_changes_snapshot_and_backtest_identity(taxonomy):
    def package(digest_character):
        return {
            "lineage": {
                "schema_version": "aurora-corpus-lineage/v1",
                "dataset_id": "package-only-lineage",
                "dataset_version": "2026-08",
                "artifact_sha256": "sha256:" + digest_character * 64,
                "manifest_sha256": "sha256:" + digest_character * 64,
            },
            "entities": [
                {"entity_type": "COMPANY", "canonical_name": "Lineage Co"}
            ],
            "sources": [
                {
                    "ref": "lineage-source",
                    "source_type": "NEWS",
                    "publisher": "Audit Wire",
                    "title": "Lineage report",
                    "excerpt": "Lineage Co launched a product.",
                }
            ],
            "observations": [
                {
                    "source_ref": "lineage-source",
                    "observation_type": "PRODUCT_LAUNCH",
                    "subject": "Lineage Co",
                    "observed_at": "2024-01-01",
                }
            ],
        }

    snapshot_a = import_package(
        package("a"), created_at="2026-08-30T00:00:00+00:00"
    )
    snapshot_b = import_package(
        package("b"), created_at="2026-08-30T00:00:00+00:00"
    )
    first = run_backtest(snapshot_a, taxonomy, ["2024-12-31"], DEFAULT_CONFIG)
    changed = run_backtest(snapshot_b, taxonomy, ["2024-12-31"], DEFAULT_CONFIG)

    assert snapshot_a.snapshot_id == snapshot_b.snapshot_id
    assert snapshot_a.input_manifest_hash() != snapshot_b.input_manifest_hash()
    assert first["backtest_manifest"]["corpus_lineage_refs"] != changed[
        "backtest_manifest"
    ]["corpus_lineage_refs"]
    assert first["backtest_identity"] != changed["backtest_identity"]


# --- source publication date (spec §19: available at the cutoff, not merely old) ---

def _src(source_id, published_at):
    from aurora.models import Source
    return Source(source_id=source_id, source_type="news", publisher="P",
                  title="t", published_at=published_at, retrieved_at="2024-01-01",
                  url_or_local_path="x", content_hash="h", independence_group="g",
                  reliability_tier="B", language="en")


def _obs(observation_id, source_id, observed_at):
    from aurora.models import Observation
    return Observation(observation_id=observation_id, source_id=source_id,
                       observed_at=observed_at, observation_type="hiring",
                       subject_entity="e1", object_entity=None, numeric_value=None,
                       unit=None, text_excerpt="t", confidence=0.9)


def test_retrospective_source_is_excluded():
    """A 2023 article about a 2020 event was not readable at a 2021 cutoff."""
    cut = leakage.apply_cutoff([_obs("o1", "s_late", "2020-05-01")],
                               [_src("s_late", "2023-06-01")], "2021-12-31")
    assert cut["observations"] == [], "a document published after the cutoff leaked in"
    assert cut["manifest"]["excluded_future_source_observation_count"] == 1
    assert cut["manifest"]["excluded_future_observation_count"] == 0, \
        "the observation itself is old; it is the document that is from the future"


def test_undated_source_is_excluded():
    """Not knowing when something became public is not evidence that it was."""
    cut = leakage.apply_cutoff([_obs("o1", "s_undated", "2020-05-01")],
                               [_src("s_undated", None)], "2021-12-31")
    assert cut["observations"] == []
    assert cut["manifest"]["excluded_undated_source_observation_count"] == 1


def test_observation_whose_source_is_missing_is_excluded():
    cut = leakage.apply_cutoff([_obs("o1", "s_absent", "2020-05-01")], [], "2021-12-31")
    assert cut["observations"] == []
    assert cut["manifest"]["excluded_undated_source_observation_count"] == 1


def test_source_published_on_the_cutoff_is_kept():
    """The boundary is inclusive on both dates; the fix must not over-reject."""
    cut = leakage.apply_cutoff([_obs("o1", "s_edge", "2020-05-01")],
                               [_src("s_edge", "2021-12-31")], "2021-12-31")
    assert [o.observation_id for o in cut["observations"]] == ["o1"]
    assert cut["manifest"]["included_observation_count"] == 1


def test_assert_no_leakage_catches_a_retrospective_source():
    """The hard re-check must see the source date, not only the event date."""
    obs = [_obs("o1", "s_late", "2020-05-01")]
    with pytest.raises(AuroraError) as exc:
        leakage.assert_no_leakage(obs, [_src("s_late", "2023-06-01")], "2021-12-31")
    assert exc.value.error_code == "FUTURE_DATA_LEAKAGE"
    assert exc.value.details["source_published_at"] == "2023-06-01"


def test_assert_no_leakage_requires_sources():
    """Calling it without sources must be impossible, not silently half-checked."""
    with pytest.raises(TypeError):
        leakage.assert_no_leakage([_obs("o1", "s", "2020-01-01")], "2021-12-31")

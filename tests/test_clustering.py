"""Clustering: two methods, separation of distinct industries, stability,
split/merge behaviour."""
from __future__ import annotations

import pytest as _pytest
pytestmark = _pytest.mark.unit
from types import SimpleNamespace

from aurora import DEFAULT_CONFIG
from aurora import clustering
from aurora.config import ClusterConfig


def test_forms_expected_number_of_clusters(snapshot):
    cl = clustering.feature_space_clusters(snapshot.entities, snapshot.observations, DEFAULT_CONFIG.clustering)
    # 3 latent + 2 mature + 2 hype + 1 failed + 1 single-giant = 9
    assert 8 <= len(cl) <= 10


def test_distinct_industries_do_not_chain(snapshot, name_to_entity):
    cl = clustering.feature_space_clusters(snapshot.entities, snapshot.observations, DEFAULT_CONFIG.clustering)
    iron = name_to_entity["FerroGrid Power"]
    myco = name_to_entity["MycoStructural"]
    neuro = name_to_entity["SpikeEdge"]
    clusters_of = {}
    for i, c in enumerate(cl):
        for e in c:
            clusters_of[e] = i
    # the three latent industries must be in three different clusters
    assert len({clusters_of[iron], clusters_of[myco], clusters_of[neuro]}) == 3


def test_two_methods_are_comparable(snapshot):
    fs = clustering.feature_space_clusters(snapshot.entities, snapshot.observations, DEFAULT_CONFIG.clustering)
    gc = clustering.graph_clusters(snapshot.entities, snapshot.observations, DEFAULT_CONFIG.clustering)
    agreement = clustering.pairwise_agreement(fs, gc)
    assert 0.0 <= agreement <= 1.0
    assert agreement > 0.3  # methods should broadly agree on this corpus


def test_stability_scores_in_range(snapshot):
    stab = clustering.stability_scores(snapshot.entities, snapshot.observations, DEFAULT_CONFIG.clustering)
    assert stab
    assert all(0.0 <= v <= 1.0 for v in stab.values())


def test_stable_industries_have_high_stability(snapshot, name_to_entity):
    stab = clustering.stability_scores(snapshot.entities, snapshot.observations, DEFAULT_CONFIG.clustering)
    # a core member of a real forming industry should be stable
    assert stab.get(name_to_entity["FerroGrid Power"], 0) >= 0.5


def test_higher_threshold_splits_more(snapshot):
    low = clustering.feature_space_clusters(snapshot.entities, snapshot.observations,
                                            ClusterConfig(similarity_threshold=0.10))
    high = clustering.feature_space_clusters(snapshot.entities, snapshot.observations,
                                             ClusterConfig(similarity_threshold=0.40))
    # tighter threshold -> at least as many (usually more) smaller clusters
    assert len(high) >= len(low) - 1


def test_large_entity_graph_uses_sparse_blocks():
    entities = [
        SimpleNamespace(entity_id=f"e{i:04d}", entity_type="COMPANY")
        for i in range(1200)
    ]
    vectors = {
        entity.entity_id: ({"shared-capability": 1.0} if i < 3 else {f"unique-{i}": 1.0})
        for i, entity in enumerate(entities)
    }
    cfg = ClusterConfig(
        similarity_threshold=0.9,
        min_cluster_size=3,
        entity_blocking_min_entities=1000,
        entity_blocking_max_block_size=128,
    )

    diagnostics = {}
    candidates = clustering.feature_space_candidate_pairs(
        [e.entity_id for e in entities], vectors, cfg, diagnostics=diagnostics,
    )
    assert candidates == [("e0000", "e0001"), ("e0000", "e0002"), ("e0001", "e0002")]
    assert diagnostics == {
        "mode": "sparse_blocking",
        "entity_count": 1200,
        "blocking_min_entities": 1000,
        "max_block_size": 128,
        "block_count": 1198,
        "accepted_block_count": 1198,
        "skipped_oversized_block_count": 0,
        "max_observed_block_size": 3,
        "complete_pair_count": 719400,
        "candidate_pair_count": 3,
        "candidate_pair_ratio": 0.00000417,
        "covered_entity_count": 1200,
        "uncovered_entity_count": 0,
        "covered_entity_ratio": 1.0,
    }
    assert clustering.feature_space_clusters([], [], cfg, vectors=vectors) == []
    clusters = clustering.feature_space_clusters(entities, [], cfg, vectors=vectors)
    assert clusters == [["e0000", "e0001", "e0002"]]


def test_sparse_blocking_diagnostics_count_skipped_high_frequency_blocks():
    entities = [
        SimpleNamespace(entity_id=f"e{i:04d}", entity_type="COMPANY")
        for i in range(1000)
    ]
    vectors = {
        entity.entity_id: ({"high-frequency": 1.0} if i < 3 else {f"unique-{i}": 1.0})
        for i, entity in enumerate(entities)
    }
    cfg = ClusterConfig(
        similarity_threshold=0.9,
        min_cluster_size=3,
        entity_blocking_min_entities=10,
        entity_blocking_max_block_size=2,
    )
    diagnostics = {}
    candidates = clustering.feature_space_candidate_pairs(
        [e.entity_id for e in entities], vectors, cfg, diagnostics=diagnostics,
    )
    assert candidates == []
    assert diagnostics["mode"] == "sparse_blocking"
    assert diagnostics["block_count"] == 998
    assert diagnostics["accepted_block_count"] == 997
    assert diagnostics["skipped_oversized_block_count"] == 1
    assert diagnostics["max_observed_block_size"] == 3
    assert diagnostics["candidate_pair_count"] == 0
    assert diagnostics["complete_pair_count"] == 499500
    assert diagnostics["covered_entity_count"] == 997
    assert diagnostics["uncovered_entity_count"] == 3
    assert diagnostics["covered_entity_ratio"] == 0.997


def test_complete_candidate_diagnostics_report_full_pair_set():
    entities = [
        SimpleNamespace(entity_id=f"e{i}", entity_type="COMPANY")
        for i in range(3)
    ]
    vectors = {e.entity_id: {e.entity_id: 1.0} for e in entities}
    diagnostics = {}
    candidates = clustering.feature_space_candidate_pairs(
        [e.entity_id for e in entities], vectors, ClusterConfig(), diagnostics=diagnostics,
    )
    assert candidates == [("e0", "e1"), ("e0", "e2"), ("e1", "e2")]
    assert diagnostics["mode"] == "complete"
    assert diagnostics["candidate_pair_count"] == 3
    assert diagnostics["complete_pair_count"] == 3
    assert diagnostics["candidate_pair_ratio"] == 1.0
    assert diagnostics["covered_entity_count"] == 3
    assert diagnostics["uncovered_entity_count"] == 0
    assert diagnostics["covered_entity_ratio"] == 1.0

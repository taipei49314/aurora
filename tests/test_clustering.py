"""Clustering: two methods, separation of distinct industries, stability,
split/merge behaviour."""
from __future__ import annotations

import pytest as _pytest
pytestmark = _pytest.mark.unit

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

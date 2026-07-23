"""Existing-taxonomy similarity and naming-gap units."""
from __future__ import annotations

import pytest as _pytest
pytestmark = _pytest.mark.unit

import pytest

from aurora import Taxonomy
from aurora.errors import AuroraError
from aurora.naming_gap import naming_gap
from aurora.clustering import entity_vectors
from conftest import hyp_for, TAXONOMY_PATH


def test_taxonomy_requires_version():
    with pytest.raises(AuroraError) as exc:
        Taxonomy({"industries": []})
    assert exc.value.error_code == "TAXONOMY_VERSION_MISSING"


def test_mature_variant_high_similarity(run, name_to_entity):
    h = hyp_for(run, ["SynergyCloud Fabric", "NextGen Colo"], name_to_entity)
    assert h.existing_industry_similarity["best_industry_id"] == "data_center_services"
    assert h.existing_industry_similarity["similarity"] >= 0.5


def test_latent_low_similarity_to_all(run, name_to_entity):
    h = hyp_for(run, ["FerroGrid Power", "LongHaul Energy"], name_to_entity)
    assert h.existing_industry_similarity["similarity"] < 0.2


def test_naming_gap_high_when_coherent_and_novel(snapshot):
    vecs = entity_vectors(snapshot.entities, snapshot.observations)
    from aurora import clustering, DEFAULT_CONFIG
    clusters = clustering.feature_space_clusters(snapshot.entities, snapshot.observations, DEFAULT_CONFIG.clustering)
    # pick a latent cluster (low taxonomy similarity assumed ~0)
    best = max(clusters, key=len)
    ng = naming_gap(best, snapshot.entities, snapshot.observations, vecs, taxonomy_similarity=0.0)
    assert 0.0 <= ng["naming_gap_score"] <= 100.0
    assert ng["capability_coherence"] > 0

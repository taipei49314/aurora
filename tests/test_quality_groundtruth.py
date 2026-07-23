"""Ground-truth quality evaluation (spec §30).

Uses the labels the corpus generator emitted (allowed in tests only) to measure
pairwise cluster precision/recall/F1 and per-archetype status accuracy. This is
the honest scorecard the engine must not peek at during discovery.
"""
from __future__ import annotations

import pytest as _pytest
pytestmark = _pytest.mark.integration

from itertools import combinations

from conftest import hyp_for

# expected terminal status per archetype family
_EXPECTED = {
    "iron_air_storage": {"INDUSTRY_CANDIDATE", "EMERGING_CAPABILITY_CLUSTER"},
    "mycelium_materials": {"INDUSTRY_CANDIDATE", "EMERGING_CAPABILITY_CLUSTER"},
    "neuromorphic_sensing": {"INDUSTRY_CANDIDATE", "EMERGING_CAPABILITY_CLUSTER"},
    "cloud_synergy_fabric": {"EXISTING_INDUSTRY_VARIANT"},
    "next_gen_mobility": {"EXISTING_INDUSTRY_VARIANT"},
    "metaverse_retail": {"HYPE_CLUSTER"},
    "quantum_blockchain": {"HYPE_CLUSTER"},
    "algae_jet_fuel": {"REJECTED", "DORMANT"},
    "ambient_holographics": {"INSUFFICIENT_EVIDENCE"},
}


def _name_to_id(snapshot):
    return {e.canonical_name: e.entity_id for e in snapshot.entities}


def test_pairwise_cluster_quality(run, snapshot, ground_truth):
    n2i = _name_to_id(snapshot)
    # ground-truth co-membership pairs (company entities only, present in map)
    gt_pairs = set()
    gt_clusters = ground_truth["clusters"]
    ent_to_gt = {}
    for key, names in gt_clusters.items():
        ids = [n2i[n] for n in names if n in n2i]
        for e in ids:
            ent_to_gt[e] = key
        for a, b in combinations(sorted(ids), 2):
            gt_pairs.add((a, b))

    pred_pairs = set()
    for h in run.hypotheses:
        ids = [e for e in h.entity_ids if e in ent_to_gt]
        for a, b in combinations(sorted(ids), 2):
            pred_pairs.add((a, b))

    tp = len(gt_pairs & pred_pairs)
    precision = tp / len(pred_pairs) if pred_pairs else 0.0
    recall = tp / len(gt_pairs) if gt_pairs else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    # strong separation is expected on this corpus
    assert precision >= 0.85, f"cluster precision too low: {precision:.2f}"
    assert recall >= 0.80, f"cluster recall too low: {recall:.2f}"
    assert f1 >= 0.82


def test_status_accuracy_per_archetype(run, snapshot, ground_truth):
    n2i = _name_to_id(snapshot)
    correct, total = 0, 0
    for key, names in ground_truth["clusters"].items():
        present = [n for n in names if n in n2i]
        h = hyp_for(run, present, n2i)
        total += 1
        if h.status in _EXPECTED[key]:
            correct += 1
    accuracy = correct / total
    assert accuracy == 1.0, f"only {correct}/{total} archetypes classified as expected"


def test_hype_recall_and_variant_recall(run, snapshot, ground_truth):
    n2i = _name_to_id(snapshot)
    for key in ("metaverse_retail", "quantum_blockchain"):
        h = hyp_for(run, [n for n in ground_truth["clusters"][key] if n in n2i], n2i)
        assert h.status == "HYPE_CLUSTER"
    for key in ("cloud_synergy_fabric", "next_gen_mobility"):
        h = hyp_for(run, [n for n in ground_truth["clusters"][key] if n in n2i], n2i)
        assert h.status == "EXISTING_INDUSTRY_VARIANT"

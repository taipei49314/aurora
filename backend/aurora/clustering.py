"""Candidate cluster formation + stability (spec §11).

Two independent methods, comparable against each other:

* ``feature_space_clusters`` — single-linkage agglomeration over cosine
  similarity of entity capability vectors (text TF-IDF + observation-type mix).
* ``graph.communities`` — label-propagation communities over the structural
  relationship graph.

Stability is tested by bootstrap: repeatedly drop a fraction of observations,
re-cluster, and measure how often each entity keeps its cluster co-membership.
Low-stability clusters are flagged and must not become industry candidates
(spec §11 last line).
"""
from __future__ import annotations

import random
from collections import defaultdict

from .features import build_entity_documents, tfidf_vectors, observation_type_vector, cosine
from .config import ClusterConfig
from . import graph as graphmod

CLUSTERABLE_TYPES = {
    "COMPANY", "TECHNOLOGY", "COMPONENT", "MATERIAL", "PROCESS", "PRODUCT",
    "APPLICATION", "FACILITY",
}


def entity_vectors(entities, observations) -> dict[str, dict[str, float]]:
    docs = build_entity_documents(entities, observations)
    tfidf = tfidf_vectors(docs)
    vecs: dict[str, dict[str, float]] = {}
    for e in entities:
        base = dict(tfidf.get(e.entity_id, {}))
        for k, v in observation_type_vector(e.entity_id, observations).items():
            base[k] = base.get(k, 0.0) + 0.5 * v  # obs-type mix as extra dims
        vecs[e.entity_id] = base
    return vecs


class _UF:
    def __init__(self, items):
        self.p = {i: i for i in items}

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            lo, hi = sorted((ra, rb))
            self.p[hi] = lo


def feature_space_candidate_pairs(
    ids, vectors: dict[str, dict[str, float]], cfg: ClusterConfig,
) -> list[tuple[str, str]]:
    """Return deterministic cosine candidates for the similarity graph.

    At the Northstar scale, the complete pair set is cheap and preserves the
    historical path. Once the entity count crosses the configured boundary,
    an inverted index over sparse vector dimensions provides blocking. A very
    high-frequency dimension is deliberately ignored: it carries little
    discriminative signal and would recreate the quadratic candidate set.
    """
    ordered_ids = sorted(ids)
    if len(ordered_ids) < cfg.entity_blocking_min_entities:
        return [
            (a, b)
            for i, a in enumerate(ordered_ids)
            for b in ordered_ids[i + 1:]
        ]

    postings: dict[str, list[str]] = defaultdict(list)
    for entity_id in ordered_ids:
        for term in sorted(vectors.get(entity_id, {})):
            postings[term].append(entity_id)

    pairs: set[tuple[str, str]] = set()
    max_block_size = max(2, int(cfg.entity_blocking_max_block_size))
    for term in sorted(postings):
        members = postings[term]
        if len(members) > max_block_size:
            continue
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                pairs.add((a, b))
    return sorted(pairs)


def feature_space_clusters(entities, observations, cfg: ClusterConfig, vectors=None):
    """Single-linkage clustering via a cosine-similarity threshold graph."""
    ents = [e for e in entities if e.entity_type in CLUSTERABLE_TYPES]
    ids = [e.entity_id for e in ents]
    vecs = vectors if vectors is not None else entity_vectors(entities, observations)
    uf = _UF(ids)
    for a, b in feature_space_candidate_pairs(ids, vecs, cfg):
        if cosine(vecs.get(a, {}), vecs.get(b, {})) >= cfg.similarity_threshold:
            uf.union(a, b)
    groups: dict[str, list[str]] = defaultdict(list)
    for i in ids:
        groups[uf.find(i)].append(i)
    clusters = [sorted(m) for m in groups.values() if len(m) >= cfg.min_cluster_size]
    clusters.sort(key=lambda m: (-len(m), m[0]))
    return clusters


def graph_clusters(entities, observations, cfg: ClusterConfig):
    clusters, _adj = graphmod.communities(
        [e for e in entities if e.entity_type in CLUSTERABLE_TYPES],
        observations, cfg.edge_min_weight, cfg.label_propagation_max_iter, cfg.min_cluster_size,
    )
    return clusters


def _co_membership(clusters) -> set[tuple[str, str]]:
    pairs = set()
    for c in clusters:
        for i in range(len(c)):
            for j in range(i + 1, len(c)):
                pairs.add((c[i], c[j]))
    return pairs


def pairwise_agreement(clusters_a, clusters_b) -> float:
    """Jaccard over co-membership pairs — how much two clusterings agree."""
    pa, pb = _co_membership(clusters_a), _co_membership(clusters_b)
    if not pa and not pb:
        return 1.0
    union = len(pa | pb)
    return len(pa & pb) / union if union else 0.0


def stability_scores(entities, observations, cfg: ClusterConfig) -> dict[str, float]:
    """For each entity, fraction of bootstrap re-clusterings in which it keeps
    at least half of its original cluster co-members."""
    base = feature_space_clusters(entities, observations, cfg)
    entity_to_cluster = {}
    for idx, c in enumerate(base):
        for e in c:
            entity_to_cluster[e] = set(c)

    rng = random.Random(cfg.random_seed)
    keep_counts: dict[str, int] = defaultdict(int)
    trials = cfg.stability_bootstrap
    for _ in range(trials):
        subset = [o for o in observations if rng.random() > cfg.stability_drop_fraction]
        clusters = feature_space_clusters(entities, subset, cfg)
        member_of = {}
        for c in clusters:
            for e in c:
                member_of[e] = set(c)
        for e, orig in entity_to_cluster.items():
            now = member_of.get(e, {e})
            others = orig - {e}
            if not others:
                keep_counts[e] += 1
                continue
            retained = len(others & now) / len(others)
            if retained >= 0.5:
                keep_counts[e] += 1
    return {e: keep_counts[e] / trials for e in entity_to_cluster}


def cluster_stability(cluster, stab: dict[str, float]) -> float:
    vals = [stab.get(e, 0.0) for e in cluster]
    return sum(vals) / len(vals) if vals else 0.0

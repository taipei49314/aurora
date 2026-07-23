"""Naming-gap analysis (spec §13).

A high naming gap means: the *capabilities* inside a cluster are highly coherent,
but the *names* used across sources to describe it are scattered — the phenomenon
has formed faster than a stable market name. We compute:

* capability_coherence  — mean pairwise cosine of member capability vectors.
* name_dispersion       — how spread out the candidate names/phrases are across
                          sources (high = no single agreed term).
* taxonomy_distance     — 1 - similarity to nearest existing industry.

naming_gap = high when coherence and taxonomy_distance are high but a single
dominant name has NOT emerged.
"""
from __future__ import annotations

import math
from collections import Counter

from .features import cosine, tokenize


def _capability_coherence(cluster, vectors) -> float:
    ids = [e for e in cluster if e in vectors]
    if len(ids) < 2:
        return 0.0
    sims, pairs = 0.0, 0
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            sims += cosine(vectors[ids[i]], vectors[ids[j]])
            pairs += 1
    return sims / pairs if pairs else 0.0


def _name_dispersion(cluster, entities, observations) -> tuple[float, list[str]]:
    """Candidate names come from entity canonical names + product-launch /
    research titles. Dispersion = 1 - (share of the single most common
    capability bigram). Many competing phrasings -> high dispersion."""
    by_id = {e.entity_id: e for e in entities}
    phrases = Counter()
    for eid in cluster:
        e = by_id.get(eid)
        if e:
            for bg in _bigrams(e.canonical_name):
                phrases[bg] += 1
    for o in observations:
        if o.subject_entity in cluster and o.observation_type in {"PRODUCT_LAUNCH", "RESEARCH_ACTIVITY"}:
            for bg in _bigrams(o.text_excerpt):
                phrases[bg] += 1
    if not phrases:
        return 0.0, []
    total = sum(phrases.values())
    top = phrases.most_common(1)[0][1]
    dispersion = 1.0 - (top / total)
    competing = [p for p, _ in phrases.most_common(5)]
    return dispersion, competing


def _bigrams(text):
    toks = tokenize(text)
    return ["_".join(toks[i:i + 2]) for i in range(len(toks) - 1)]


def naming_gap(cluster, entities, observations, vectors, taxonomy_similarity: float) -> dict:
    coherence = _capability_coherence(cluster, vectors)
    dispersion, competing = _name_dispersion(cluster, entities, observations)
    taxonomy_distance = 1.0 - taxonomy_similarity
    # gap is high only when the field is coherent AND far from known industries
    # AND names are dispersed.
    raw = coherence * dispersion * taxonomy_distance
    score = 100.0 * (raw ** 0.5)  # sqrt to spread the low end
    return {
        "naming_gap_score": round(min(100.0, score), 2),
        "capability_coherence": round(coherence, 4),
        "name_dispersion": round(dispersion, 4),
        "taxonomy_distance": round(taxonomy_distance, 4),
        "competing_names": competing,
    }

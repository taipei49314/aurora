"""Deterministic feature construction (spec §9).

No external LLM, no fixed industry-keyword list. Features are built only from
the data: text (TF-IDF + n-grams), observation-type mix, source-type mix, and
entity co-occurrence. Everything here is a pure function of the input, so it is
fully reproducible and replayable.

The key object is an *entity capability profile*: a sparse weighted vector that
mixes textual capability terms with structural signals (which technologies /
components / processes an entity is linked to via observations). Cluster
formation must reflect this combination, never article counts alone (spec §11).
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

from .models import Entity, Observation

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-\+]*")

# Generic stopwords only. Deliberately contains NO industry/technology terms so
# the engine cannot be biased toward "ai/robot/quantum" (spec §5.3).
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with", "by",
    "is", "are", "as", "at", "from", "that", "this", "it", "its", "be", "will",
    "we", "our", "their", "has", "have", "new", "using", "used", "into", "than",
    "per", "via", "over", "more", "also", "which", "these", "those", "was", "were",
}


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOPWORDS and len(t) > 1]


def ngrams(tokens: list[str], n: int = 2) -> list[str]:
    return ["_".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def _doc_terms(text: str) -> Counter:
    toks = tokenize(text)
    c = Counter(toks)
    for bg in ngrams(toks, 2):
        c[bg] += 1
    return c


def build_entity_documents(entities, observations) -> dict[str, str]:
    """Aggregate all text associated with each entity into one pseudo-document.

    Includes the entity's own description plus the text of every observation in
    which it is the subject, plus the *canonical names of linked object
    entities* (so a company that repeatedly depends on the same technology gets
    that technology's terms in its profile — this is what makes structurally
    related companies cluster together).
    """
    by_id = {e.entity_id: e for e in entities}
    docs: dict[str, list[str]] = defaultdict(list)
    for e in entities:
        docs[e.entity_id].append(e.description)
        docs[e.entity_id].append(e.canonical_name)
    for o in observations:
        # Only *content* terms feed the text profile. We deliberately do NOT add
        # observation-type words ("patent activity", ...) or object entity-type
        # words ("component", ...) because those are shared across every cluster
        # and would cause single-linkage chaining that merges distinct
        # industries. Observation-type mix is captured separately as low-weight
        # ``obs::`` dimensions in ``clustering.entity_vectors``.
        docs[o.subject_entity].append(o.text_excerpt)
        if o.object_entity and o.object_entity in by_id:
            # a linked object contributes its cluster-specific NAME only
            docs[o.subject_entity].append(by_id[o.object_entity].canonical_name)
    return {eid: " . ".join(t for t in parts if t) for eid, parts in docs.items()}


def tfidf_vectors(entity_docs: dict[str, str]) -> dict[str, dict[str, float]]:
    """Standard TF-IDF with L2 normalization. Deterministic given input."""
    term_counts: dict[str, Counter] = {eid: _doc_terms(doc) for eid, doc in entity_docs.items()}
    n_docs = max(1, len(term_counts))
    df: Counter = Counter()
    for c in term_counts.values():
        for term in c:
            df[term] += 1
    vectors: dict[str, dict[str, float]] = {}
    for eid, counts in term_counts.items():
        total = sum(counts.values()) or 1
        vec: dict[str, float] = {}
        for term, tf in counts.items():
            idf = math.log((1 + n_docs) / (1 + df[term])) + 1.0
            vec[term] = (tf / total) * idf
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vectors[eid] = {t: v / norm for t, v in vec.items()}
    return vectors


def observation_type_vector(entity_id: str, observations) -> dict[str, float]:
    c = Counter(o.observation_type for o in observations if o.subject_entity == entity_id)
    total = sum(c.values()) or 1
    return {f"obs::{k}": v / total for k, v in c.items()}


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors. Iterates the smaller."""
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values())) or 1.0
    nb = math.sqrt(sum(v * v for v in b.values())) or 1.0
    return dot / (na * nb)


def entity_cooccurrence(observations) -> dict[tuple[str, str], float]:
    """Weighted co-occurrence between subject and object entities across
    observations. Weighted by observation confidence. Symmetric keys are stored
    as sorted tuples so lookups are order-independent."""
    w: dict[tuple[str, str], float] = defaultdict(float)
    for o in observations:
        if o.object_entity and o.object_entity != o.subject_entity:
            key = tuple(sorted((o.subject_entity, o.object_entity)))
            w[key] += float(o.confidence or 1.0)
    return dict(w)

"""Entity relationship graph + community detection (spec §11 method 2).

The graph is built from *structural* relationships (co-occurrence, supplier,
customer, technical dependency, strategic investment), not from article counts.
Communities are found with deterministic label propagation: nodes are processed
in sorted order, each adopts the highest-weighted neighbor label, ties broken by
smallest label id. This is stable and seed-independent.
"""
from __future__ import annotations

from collections import defaultdict

from .features import entity_cooccurrence

RELATIONAL_TYPES = {
    "SUPPLIER_RELATIONSHIP", "CUSTOMER_RELATIONSHIP", "TECHNICAL_DEPENDENCY",
    "STRATEGIC_INVESTMENT",
}


def build_graph(entities, observations, edge_min_weight: float) -> dict[str, dict[str, float]]:
    """Weighted undirected adjacency. Combines co-occurrence with explicit
    relational observations (which get extra weight)."""
    valid_ids = {e.entity_id for e in entities}
    adj: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for (a, b), w in entity_cooccurrence(observations).items():
        if a in valid_ids and b in valid_ids:
            adj[a][b] += w
            adj[b][a] += w

    for o in observations:
        if o.observation_type in RELATIONAL_TYPES and o.object_entity:
            a, b = o.subject_entity, o.object_entity
            if a in valid_ids and b in valid_ids and a != b:
                bonus = 1.5 * float(o.confidence or 1.0)
                adj[a][b] += bonus
                adj[b][a] += bonus

    # normalize by max edge weight so threshold is scale-free
    max_w = max((w for nbrs in adj.values() for w in nbrs.values()), default=1.0)
    pruned: dict[str, dict[str, float]] = {}
    for a, nbrs in adj.items():
        kept = {b: w / max_w for b, w in nbrs.items() if w / max_w >= edge_min_weight}
        if kept:
            pruned[a] = kept
    return pruned


def label_propagation(adj: dict[str, dict[str, float]], max_iter: int) -> dict[str, str]:
    """Deterministic label propagation community detection."""
    nodes = sorted(adj.keys())
    labels = {n: n for n in nodes}
    for _ in range(max_iter):
        changed = False
        for n in nodes:  # sorted order -> deterministic
            weight_by_label: dict[str, float] = defaultdict(float)
            for nbr, w in adj[n].items():
                weight_by_label[labels[nbr]] += w
            if not weight_by_label:
                continue
            # pick max weight, tie-break by smallest label id
            best = min(weight_by_label.items(), key=lambda kv: (-kv[1], kv[0]))[0]
            if labels[n] != best:
                labels[n] = best
                changed = True
        if not changed:
            break
    return labels


def communities(entities, observations, edge_min_weight: float, max_iter: int, min_size: int):
    adj = build_graph(entities, observations, edge_min_weight)
    labels = label_propagation(adj, max_iter)
    groups: dict[str, list[str]] = defaultdict(list)
    for node, lab in labels.items():
        groups[lab].append(node)
    clusters = [sorted(members) for members in groups.values() if len(members) >= min_size]
    # deterministic ordering: by size desc then first member id
    clusters.sort(key=lambda m: (-len(m), m[0]))
    return clusters, adj

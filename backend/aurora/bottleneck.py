"""Bottleneck analysis (spec §18).

Finds nodes that are hardest to substitute / most likely to constrain growth.
Crucially, a bottleneck is identified from *structural position and scarcity*,
never from company size or news volume — so a small, rarely-mentioned entity on
many dependency paths ranks highly (Scenario D).

Betweenness centrality is computed with Brandes' algorithm on the cluster
subgraph. Substitutability is derived from the data (how many alternative
entities supply the same role), not hardcoded.
"""
from __future__ import annotations

from collections import defaultdict, deque

from .models import BottleneckCandidate

_BN_WEIGHTS = {
    "centrality": 0.30,
    "low_substitutability": 0.22,
    "supplier_concentration": 0.14,
    "lead_time": 0.12,
    "capacity_constraint": 0.10,
    "cross_cluster_dependency": 0.12,
}


def _brandes_betweenness(nodes, adj) -> dict[str, float]:
    """Unweighted betweenness centrality (deterministic)."""
    cb = {v: 0.0 for v in nodes}
    for s in sorted(nodes):
        S, P, sigma, dist = [], defaultdict(list), dict.fromkeys(nodes, 0.0), dict.fromkeys(nodes, -1)
        sigma[s], dist[s] = 1.0, 0
        Q = deque([s])
        while Q:
            v = Q.popleft()
            S.append(v)
            for w in sorted(adj.get(v, {})):
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    Q.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    P[w].append(v)
        delta = dict.fromkeys(nodes, 0.0)
        while S:
            w = S.pop()
            for v in P[w]:
                if sigma[w] > 0:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
            if w != s:
                cb[w] += delta[w]
    n = len(nodes)
    scale = ((n - 1) * (n - 2)) if n > 2 else 1
    return {v: cb[v] / scale for v in nodes}


def analyze(hypothesis_id, cluster, entities, observations, all_clusters, adj):
    by_id = {e.entity_id: e for e in entities}
    nodes = [c for c in cluster if c in by_id]
    sub_adj = {n: {m: w for m, w in adj.get(n, {}).items() if m in cluster} for n in nodes}
    centrality = _brandes_betweenness(nodes, sub_adj)

    # who supplies the same role -> substitutability. Count entities that are the
    # "from" of a SUPPLIER/TECHNICAL_DEPENDENCY edge grouped by the role they fill.
    suppliers_by_target = defaultdict(set)   # (dep type, downstream) -> upstream suppliers
    downstream_of = defaultdict(set)
    for o in observations:
        if o.subject_entity in cluster and o.object_entity in cluster:
            if o.observation_type in {"SUPPLIER_RELATIONSHIP", "TECHNICAL_DEPENDENCY"}:
                # object is the depended-on upstream; subject depends on it
                suppliers_by_target[o.observation_type + ":" + o.subject_entity].add(o.object_entity)
                downstream_of[o.object_entity].add(o.subject_entity)

    # cross-cluster dependency: entity depended on by entities outside its cluster
    cluster_of = {}
    for idx, c in enumerate(all_clusters):
        for e in c:
            cluster_of[e] = idx
    cross_dep = defaultdict(set)
    for o in observations:
        if o.observation_type in {"SUPPLIER_RELATIONSHIP", "TECHNICAL_DEPENDENCY"} and o.object_entity:
            if cluster_of.get(o.subject_entity) is not None and cluster_of.get(o.object_entity) is not None:
                if cluster_of[o.subject_entity] != cluster_of[o.object_entity]:
                    cross_dep[o.object_entity].add(cluster_of[o.subject_entity])

    # capacity / lead-time pressure from observations
    lead_time = defaultdict(float)
    capacity = defaultdict(float)
    for o in observations:
        if o.subject_entity in cluster:
            if o.observation_type == "LEAD_TIME_PRESSURE":
                lead_time[o.subject_entity] = max(lead_time[o.subject_entity], min(1.0, (o.numeric_value or 12) / 24.0))
            if o.observation_type == "CAPACITY_EXPANSION" and (o.numeric_value or 0) < 0:
                capacity[o.subject_entity] = 1.0

    # alternatives must serve the *same need*: co-suppliers of the same downstream
    # via the same dependency type. A co-listed supplier of a different type
    # (e.g. the component entity next to its supplier) is not a substitute.
    alt_by_entity = defaultdict(set)
    for suppliers in suppliers_by_target.values():
        for s in suppliers:
            alt_by_entity[s] |= suppliers - {s}

    candidates = []
    for e in nodes:
        downstream = downstream_of.get(e, set())
        alt_suppliers = alt_by_entity.get(e, set())
        substitutability = min(1.0, len(alt_suppliers) / 2.0)  # 0 alts -> 0, 2+ -> 1
        low_sub = 1.0 - substitutability
        supplier_conc = 1.0 if downstream and not alt_suppliers else (0.5 if len(alt_suppliers) == 1 else 0.0)
        cross = min(1.0, len(cross_dep.get(e, set())) / 2.0)
        cen = centrality.get(e, 0.0)
        # normalize centrality within cluster
        max_cen = max(centrality.values()) or 1.0
        cen_norm = cen / max_cen if max_cen else 0.0

        factors = {
            "centrality": cen_norm,
            "low_substitutability": low_sub if downstream else 0.0,
            "supplier_concentration": supplier_conc,
            "lead_time": lead_time.get(e, 0.0),
            "capacity_constraint": capacity.get(e, 0.0),
            "cross_cluster_dependency": cross,
        }
        score = 100.0 * sum(_BN_WEIGHTS[k] * v for k, v in factors.items())
        if not downstream and cen_norm == 0.0:
            continue  # not on any dependency path
        candidates.append(BottleneckCandidate(
            entity_id=e,
            hypothesis_id=hypothesis_id,
            bottleneck_score=round(score, 2),
            centrality=round(cen_norm, 4),
            supplier_concentration=round(supplier_conc, 4),
            substitutability=round(substitutability, 4),
            lead_time=round(lead_time.get(e, 0.0), 4),
            capacity_constraint=round(capacity.get(e, 0.0), 4),
            cross_cluster_dependency=round(cross, 4),
            failure_impact=round(min(1.0, len(downstream) / 3.0), 4),
            evidence_confidence=0.8,
            limits_what=f"supply of the capability provided by {by_id[e].canonical_name}",
            downstream_dependents=sorted(downstream),
            substitute_exists=bool(alt_suppliers),
            substitution_time_note="qualification typically multi-quarter" if not alt_suppliers else "alternatives exist",
            scarcity_evidence_ids=[o.observation_id for o in observations
                                   if o.subject_entity == e and o.observation_type in {"LEAD_TIME_PRESSURE", "CAPACITY_EXPANSION"}],
            disconfirming_data_note="new qualified suppliers or a substitute technology would remove this bottleneck",
        ))
    candidates.sort(key=lambda c: (-c.bottleneck_score, c.entity_id))
    top_score = candidates[0].bottleneck_score if candidates else 0.0
    return {"candidates": candidates, "bottleneck_score": top_score}

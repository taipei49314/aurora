# Clustering Model (spec §11)

## Two independent methods
1. **Feature-space single-linkage** (`clustering.feature_space_clusters`).
   Entity capability vectors = TF-IDF over entity documents (description, own
   text, linked-object *names*) + low-weight `obs::TYPE` dimensions. Two entities
   are linked if cosine ≥ `similarity_threshold`; connected components ≥
   `min_cluster_size` become clusters.
2. **Graph community detection** (`graph.communities`). A weighted relationship
   graph (co-occurrence + supplier/customer/technical-dependency/investment
   edges) is partitioned by **deterministic label propagation** (sorted node
   order, highest-weighted neighbor label, ties → smallest label id).

`pairwise_agreement` (Jaccard over co-membership pairs) lets the two be compared;
on Northstar they agree ~0.56.

## Chaining hazard (fixed)
Single-linkage chains through shared terms. Early versions merged all three
latent industries because every company document contained shared
observation-type words ("patent activity", "hiring activity", …). Fix: the text
profile carries **only content terms** — obs-type mix is kept as separate
low-weight dimensions. Verified by
`test_clustering.py::test_distinct_industries_do_not_chain`.

## Stability (bootstrap)
`stability_scores` drops a fixed fraction of observations `stability_bootstrap`
times (seeded) and measures how often each entity keeps ≥half its cluster
co-members. Clusters below `min_stability` cannot become candidates
(`classify.py` gate 5).

## Split / merge / drift
Comparing clusterings across runs/cutoffs (via `divergence.compare` and the
backtest track-matching by entity Jaccard) surfaces split, merge, drift and
disappearance over time.

## Scale / performance
Source near-duplicate detection uses **MinHash-LSH** (`dedup.py`, 48 hashes /
12 bands of 4), so it stays near-linear at 3120 sources instead of O(sources²).
The entity pairwise cosine is O(entities²) = 199² and, with the 8× stability
bootstrap, dominates the ~1.6 s pipeline at full scale — acceptable here, and a
candidate for entity blocking beyond ~1k entities. Thresholds are unchanged by
these optimizations.

# Bottleneck Model (spec §18)

## Purpose and source of truth

The bottleneck stage ranks entities that occupy scarce or structurally important
positions inside one feature-space cluster. It does not use company size or news
volume as a ranking factor. The executable definition is
`backend/aurora/bottleneck.py`; the graph it receives is built by
`backend/aurora/graph.py`, and `backend/aurora/pipeline.py` connects the result to
scoring and the API.

This is a deterministic research heuristic. A high score means that the current
input graph and pressure observations make an entity look constraining; it is not
proof of a real-world shortage or an estimate of financial impact.

## Inputs

`bottleneck.analyze` receives:

- a `hypothesis_id` and the entity ids in its feature-space `cluster`;
- all imported entities and the cutoff-filtered observations;
- all feature-space clusters, used to identify cross-cluster dependencies; and
- the pruned entity adjacency from `graph.build_graph`.

The adjacency is an undirected graph. It combines subject/object co-occurrence
with an extra weight for explicit supplier, customer, technical-dependency and
strategic-investment observations, normalizes by the largest edge weight, and
removes edges below `ClusterConfig.edge_min_weight` (currently `0.12`). The
bottleneck centrality calculation uses the surviving topology, not the edge
weights.

Three observation types supply additional bottleneck factors:

- `SUPPLIER_RELATIONSHIP` and `TECHNICAL_DEPENDENCY` establish upstream and
  downstream structure. In both cases the observation subject depends on its
  object.
- `LEAD_TIME_PRESSURE` supplies the lead-time factor.
- a `CAPACITY_EXPANSION` observation with a negative `numeric_value` supplies a
  capacity-constraint flag.

## Algorithm and decision boundaries

1. Restrict the adjacency to the cluster and compute unweighted Brandes
   betweenness centrality in sorted node order. Divide every value by the maximum
   centrality in that cluster, producing `centrality` in `0..1`.
2. For each dependency type and downstream subject, collect its upstream object
   entities. Two suppliers count as alternatives only when they serve the same
   downstream entity through the same dependency type. This prevents a co-listed
   component with a different relationship from being treated as a substitute.
3. Derive `substitutability = min(1, alternative_count / 2)`. No alternatives
   gives `0`; one gives `0.5`; two or more gives `1`. `low_substitutability` is
   `1 - substitutability`, but contributes only when the entity has a downstream
   dependent.
4. Derive supplier concentration as `1.0` when an entity has downstream demand
   and no alternative, `0.5` with one alternative, otherwise `0.0`.
5. Count distinct feature-space clusters that contain entities depending on the
   candidate, and cap `cross_cluster_dependency` at `1.0` after two clusters.
6. Normalize lead-time pressure as `min(1, numeric_value / 24)`. The current code
   substitutes `12` when the value is missing or falsey. Capacity constraint is
   binary: `1.0` only for a negative capacity-expansion value, otherwise `0.0`.
7. Compute the score:

   ```text
   bottleneck_score = 100 * (
       0.30 * centrality
     + 0.22 * low_substitutability
     + 0.14 * supplier_concentration
     + 0.12 * lead_time
     + 0.10 * capacity_constraint
     + 0.12 * cross_cluster_dependency
   )
   ```

8. Drop an entity only when it has no downstream dependents and zero normalized
   centrality. Sort the remaining candidates by descending score, then by
   `entity_id`. The first score becomes the cluster-level `bottleneck_score`.

All weights and thresholds above are literal current implementation values.
Unlike overall scoring and clustering thresholds, the factor weights live in
`bottleneck.py`, not in `EngineConfig`.

## Outputs and provenance

Each `BottleneckCandidate` records the factor values, downstream entity ids,
whether an alternative exists, a short limitation description, and
`scarcity_evidence_ids` for lead-time or negative capacity observations attached
to that candidate. Positive capacity-expansion observations are excluded from
this scarcity provenance. The analyzer returns the complete sorted candidate list and
the top score.

The pipeline:

- uses the top score as the `bottleneck_score` component of the transparent
  overall score;
- stores the top five serialized candidates in
  `hypothesis.score_explanation["bottlenecks"]`; and
- exposes that list through `GET /api/hypotheses/{hyp_id}/bottlenecks`.

Structural dependency ids are visible through `downstream_dependents`, but the
current candidate record does not carry the observation ids for every graph edge.
`evidence_confidence` is currently the constant `0.8`, and
`substitution_time_note` is selected from two fixed strings; neither is a
measured confidence interval or sourced qualification-time estimate.

## Boundaries and known limits

- Centrality is unweighted after graph pruning. Edge confidence affects whether
  an edge survives and the graph normalization, but not shortest-path length.
- Alternatives are inferred from same-downstream, same-relation co-supply. The
  model does not evaluate technical equivalence, price, geography, contracts,
  available capacity, or qualification status.
- The import schema recommends `months` for lead-time values, but the analyzer
  does not inspect `unit`; incorrectly scaled input changes the score.
- Missing lead-time values on `LEAD_TIME_PRESSURE` observations receive the
  current 12-month fallback. That is a heuristic default, not observed evidence.
  Negative values are clamped at the existing zero floor and do not reduce the
  score below zero.
- Capacity pressure recognizes only a negative `CAPACITY_EXPANSION` numeric
  value. It does not infer pressure from prose or normalize physical units.
- Cross-cluster dependency depends on the current feature-space partition.
  Entities absent from those clusters do not contribute to that factor.
- The model ranks candidates inside observed structure. It cannot detect an
  omitted supplier, dependency, substitute, or pressure event.

## Verification

- `tests/test_hype_counterevidence_bottleneck.py::test_bottleneck_ranking_is_structural_not_volume`
  checks that the structurally central supplier is surfaced.
- `tests/test_scenarios.py::test_scenario_d_small_supplier_is_top_bottleneck`
  checks that a small supplier outranks the news-heavy integrator.
- `tests/test_scenarios.py::test_scenario_d_shared_supplier_has_no_false_substitutes`
  locks the same-downstream, same-dependency-type substitute rule and expects
  zero substitutability when no true co-supplier exists.
- No dedicated test locks every factor weight and normalization rule. Review
  those literals against `backend/aurora/bottleneck.py`; the complete engine
  gate is available through `python scripts/check_engine.py`.

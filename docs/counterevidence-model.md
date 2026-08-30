# Counterevidence Model (spec §16)

Every hypothesis must expose evidence that could weaken or falsify it. The
implementation in `backend/aurora/counterevidence.py` returns supporting
evidence, negative evidence, missing expected signal types, structural warning
flags, and explicit disconfirmation conditions. A cluster is never promoted
solely because its positive score is high.

## Evidence sets

The analysis uses cutoff-filtered observations whose subject belongs to the
cluster.

- Supporting evidence uses positive real-investment observations plus
  `DEMAND_TYPES` from `models.py`. A `CAPACITY_EXPANSION` with a negative
  `numeric_value` is excluded from this set.
- Counterevidence uses `NEGATIVE_TYPES`—cancellations, shutdowns, price
  pressure, and lead-time pressure—plus negative capacity-expansion values.
- Both lists are sorted by descending confidence and stable observation id; the
  first five ids are retained on the hypothesis.

The following expected observation types are reported as missing when absent:

```text
PATENT_ACTIVITY, HIRING_ACTIVITY, CAPEX_ACTIVITY,
SUPPLIER_RELATIONSHIP, CUSTOMER_RELATIONSHIP,
STANDARD_ACTIVITY, ADOPTION_SIGNAL
```

Missing evidence is a diagnostic list. It is not fabricated evidence and does
not by itself assert that a hypothesis is false.

## Contradiction score

Let `negative` be the number of negative observations and `total` the number of
cluster observations (with a denominator floor of one):

```text
contradiction = 100 * min(1, (negative / total) / 0.25)
```

The model also measures the largest subject's share of cluster observations. A
cluster with at least two entities is `single_entity_driven` when that share is
greater than `0.70`; its contradiction score is then floored at `55`.

The pipeline subtracts contradiction through
`ScoringConfig.contradiction_penalty_weight` (`0.40`). Classification marks a
cluster dormant at `45` and rejected at `70`, subject to the rest of the status
gates.

## Disconfirmation and provenance

The output always includes explicit conditions covering supplier exits,
reversed hiring, failed repeat adoption, substitute displacement, persistent
scale pressure, and single-entity dependence. These are model-level tests a
future run can evaluate; they are not claims that the events already occurred.

The hypothesis preserves:

- `strongest_supporting_evidence` and `strongest_counterevidence` ids;
- `missing_evidence`;
- `disconfirmation_conditions`; and
- the numeric contradiction score used by scoring and classification.

## Boundaries

- The contradiction ratio is count-based. Observation confidence controls the
  top-five ordering but does not weight the ratio.
- Capacity signs are semantic: a missing, zero, or positive expansion amount is
  treated as positive investment, while a negative amount is a contraction.
- The expected-signal list and disconfirmation text are controlled model
  policy, not learned from the corpus.
- The `dedup_resolved_group` argument is currently accepted by `analyze` but is
  not used there. Source independence is computed elsewhere in the pipeline.
- Temporal collapse is mentioned in the module intent but is not a separate
  implemented penalty in the current function; date effects enter through the
  cutoff and the observations available to the analysis.

## Verification

- `tests/test_hype_counterevidence_bottleneck.py` verifies that contradiction
  subtracts from the overall score and that missing signals are reported.
- `tests/test_scenarios.py` Scenario F requires failed clusters to become
  `DORMANT` or `REJECTED` with counterevidence and disconfirmation conditions.
- `tests/test_properties.py` verifies that increasing a penalty cannot improve
  the assembled score.

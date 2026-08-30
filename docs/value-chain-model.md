# Value-Chain Model (spec §17)

The value-chain stage assigns an interpretable role to each entity in a cluster
and emits evidence-linked dependency edges. Its implementation is
`backend/aurora/value_chain.py`; the pipeline stores the result in each
hypothesis's `score_explanation`.

## Inputs and node roles

`build` receives a hypothesis id, the cluster's entity ids, all normalized
entities, and the cutoff-filtered observations. Entities are processed in
sorted id order. Their default roles come from entity type:

| Entity type | Role |
|---|---|
| `MATERIAL` | `RAW_INPUT` |
| `COMPONENT`, `TECHNOLOGY` | `CORE_COMPONENT` |
| `FACILITY` | `ENABLING_EQUIPMENT` |
| `PROCESS` | `PROCESS` |
| `PRODUCT`, `COMPANY` | `INTEGRATION` |
| `APPLICATION` | `APPLICATION` |
| `MARKET` | `END_CUSTOMER` |
| `STANDARD_BODY`, `GOVERNMENT` | `STANDARD_OR_REGULATION` |

A `COMPANY` with a missing, zero, or positive `CAPACITY_EXPANSION` value is
promoted to `INFRASTRUCTURE`; a negative value is a contraction and does not
promote the role. Research organizations, people, and provisional entities use
the low-specificity `INTEGRATION` fallback; this does not make them confirmed
integrators outside this model.

Every `ValueChainNode` carries the ids of observations where that entity is the
subject. Node ids are content-addressed from the hypothesis and entity ids.

## Confirmed edges and direction

Only observations whose subject and object are both inside the cluster can
produce an edge. The accepted relationship types are:

- `SUPPLIER_RELATIONSHIP` and `TECHNICAL_DEPENDENCY`: object → subject;
- `CUSTOMER_RELATIONSHIP`: subject → object.

Each emitted edge is marked `CONFIRMED` and includes the originating
observation id. The current implementation does not synthesize co-occurrence
edges, so `INFERRED_LOW_CONFIDENCE` is a design boundary rather than a value
currently emitted by `build`.

## Completeness score and downstream use

The completeness denominator contains seven roles:

```text
RAW_INPUT, CORE_COMPONENT, ENABLING_EQUIPMENT, PROCESS,
INTEGRATION, APPLICATION, END_CUSTOMER
```

`value_chain_score` is the percentage of those roles present at least once.
Counts of entities, edges, or observations do not increase it. The score has a
`0.12` weight in `ScoringConfig`; `ClassificationConfig` requires at least
`45.0` before a cluster can become an `INDUSTRY_CANDIDATE`.

`INFRASTRUCTURE` is a more specific company label but satisfies the
`INTEGRATION` coverage slot. A positive capacity observation therefore cannot
reduce completeness merely by relabeling a company.

The pipeline preserves:

- serialized nodes and confirmed edges under `score_explanation.value_chain`;
- the sorted role set under `score_explanation.value_chain_roles`; and
- the numeric completeness score on the hypothesis.

## Boundaries

- Role assignment is rule-based and uses entity/observation controlled
  vocabularies; it does not infer business function from prose.
- Completeness measures role coverage, not economic scale, capacity, market
  power, or causal certainty.
- Node evidence currently includes all subject observations, not only evidence
  specific to the assigned role.
- `PERSON`, `PROVISIONAL`, and research-organization fallbacks are deliberately
  conservative and should not be presented as externally verified roles.
- Bottleneck analysis consumes the relational structure separately and must not
  be inferred from the completeness score alone.

## Verification

- `tests/test_scenarios.py` exercises the candidate value-chain gate as part of
  the end-to-end A–H acceptance scenarios and requires hypothesis provenance.
- `tests/test_hype_counterevidence_bottleneck.py` verifies capacity-sign role
  behavior, completeness monotonicity, and downstream bottleneck provenance;
  Scenario D covers the structural dependency path end to end.
- Changes to role mapping, edge direction, or completeness roles should add a
  focused unit regression in addition to the end-to-end scenarios.

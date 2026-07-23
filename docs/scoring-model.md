# Scoring Model (spec §14)

No mysterious AI score. `overall` is a documented linear combination of 0..100
component scores minus explicit penalties, all driven by `config.ScoringConfig`.

```
weighted_sum = Σ  w_i · score_i           (positive weights sum to 1.0)
overall      = clip( weighted_sum
                     − hype_pen·(hype/100)·weighted_sum
                     − contra_pen·(contradiction/100)·weighted_sum
                     − dq_pen·data_quality_penalty , 0, 100 )
```

## Components (each 0..100)
| component | source | meaning |
|---|---|---|
| novelty_score | `100·(1−taxonomy_similarity)` | distance from known industries |
| coherence_score | capability coherence | how tightly the cluster hangs together |
| acceleration_score | mean entity acceleration | signals rising, not a one-off |
| value_chain_score | `value_chain.build` | fraction of chain roles present |
| real_investment_score | saturating(real-obs ratio, 0.35) | patents/hiring/capex/supply/standards |
| demand_score | saturating(demand ratio, 0.18) | customers/adoption/demand-pull |
| bottleneck_score | top bottleneck | scarcity structure present |
| naming_gap_score | `naming_gap` | coherent field, no agreed name |
| source_independence_score | saturating(independent groups, 5) | not one syndicated source |
| cluster_stability_score | bootstrap stability | robust to data perturbation |

## Penalties (subtracted)
- **hype** and **contradiction** scale the weighted sum down — loud noise or
  counterevidence can never *raise* the score (verified by
  `test_penalties_never_increase_score`).
- **data_quality_penalty** subtracts for missing dates / low-confidence obs.

## Transparency (UI/API)
`hypothesis.score_explanation.scoring` returns every component score, its weight,
its contribution, the three penalty amounts, the confidence band, and the
formula string. Changing any weight forces a new immutable run.

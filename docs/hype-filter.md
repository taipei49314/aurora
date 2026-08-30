# Hype Filter (spec §15)

Separates genuine industry formation from narrative hype. Output is a 0..100
`hype_risk_score` from transparent sub-factors (each 0..1, 1 = most hype-like):

| factor | weight | high when |
|---|---|---|
| narrative_dominance | 0.24 | news/product-launch/investment dominate real activity |
| low_real_investment | 0.20 | few positive patents/hiring/capex/supply-chain observations |
| low_demand | 0.16 | few customer/adoption/demand signals |
| low_independence | 0.18 | many reprints of few independent releases |
| no_supply_chain | 0.10 | no supplier/technical-dependency/positive-capacity signals |
| no_standards_or_contracts | 0.06 | no standards/regulatory activity |
| faded | 0.06 | dated activity peaked in an earlier calendar window, then collapsed in the recent window |

`overall` subtracts a hype penalty proportional to this score, so a high-volume
cluster **cannot** rank first on noise alone.

A `CAPACITY_EXPANSION` with a negative numeric value is a contraction: it does
not lower hype risk as real investment or supply-chain evidence.

## Temporal fade

`faded` compares counts in three **equal-length calendar windows** ending at
the evaluation date. It is `1 - recent / max(early, middle)`, clamped to
`0..1`; activity that is uniform or rising therefore does not count as faded.
At least six dated observations are required. Undated or malformed dates do
not satisfy that minimum and cannot create a fade signal.

`hype_assessment(cluster, observations, as_of=...)` accepts an explicit ISO
evaluation date. Historical runs should pass their cutoff date as `as_of`, so
the final window includes any silence between the last observation and the
cutoff. Observations after `as_of` are excluded from this temporal factor. For
backward compatibility, omitting `as_of` anchors the windows at the latest
valid observation date.

The returned `fade_analysis` records the anchor, window boundaries/counts,
excluded future rows, undated rows, and the minimum-observation threshold for
auditability.

## Buzzword neutrality (spec §5.3)
There is no keyword list and no bonus for "ai/robot/quantum". The Northstar
`quantum_blockchain` cluster scores **hype 95 → overall 11.7**, below every real
candidate — verified by `test_scenarios.py::test_scenario_b_quantum_buzzword_not_inflated`.

## Single-giant vs hype (Scenario E vs B)
- **Single giant**: many signals, but ~1 independent source group and one
  entity → caught by the *insufficiency* gate (`independent_sources < 3`).
- **Hype**: many companies and independent releases, but low real
  investment/demand + heavy reprinting → caught by the *hype* gate.
These are deliberately different discriminators (`classify.py`).

# Hype Filter (spec §15)

Separates genuine industry formation from narrative hype. Output is a 0..100
`hype_risk_score` from transparent sub-factors (each 0..1, 1 = most hype-like):

| factor | weight | high when |
|---|---|---|
| narrative_dominance | 0.24 | news/product-launch/investment dominate real activity |
| low_real_investment | 0.20 | few patents/hiring/capex/supply-chain observations |
| low_demand | 0.16 | few customer/adoption/demand signals |
| low_independence | 0.18 | many reprints of few independent releases |
| no_supply_chain | 0.10 | no supplier/technical-dependency/capacity signals |
| no_standards_or_contracts | 0.06 | no standards/regulatory activity |
| faded | 0.06 | activity spiked then collapsed in the last third |

`overall` subtracts a hype penalty proportional to this score, so a high-volume
cluster **cannot** rank first on noise alone.

## Buzzword neutrality (spec §5.3)
There is no keyword list and no bonus for "ai/robot/quantum". The Northstar
`quantum_blockchain` cluster scores **hype 89 → overall 27.9**, below every real
candidate — verified by `test_scenarios.py::test_scenario_b_quantum_buzzword_not_inflated`.

## Single-giant vs hype (Scenario E vs B)
- **Single giant**: many signals, but ~1 independent source group and one
  entity → caught by the *insufficiency* gate (`independent_sources < 3`).
- **Hype**: many companies and independent releases, but low real
  investment/demand + heavy reprinting → caught by the *hype* gate.
These are deliberately different discriminators (`classify.py`).

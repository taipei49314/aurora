# Scorecard — iron-air-retro

## Proven (when `make retro-case` is green)

| Gate | Meaning |
|------|---------|
| Zero leakage | No post-cutoff `observed_at` enters any cutoff run |
| Early weakness | 2020-12-31 best overall stays below candidate-ish band; no `INDUSTRY_CANDIDATE` |
| Mid patents | 2022-12-31 includes `PATENT_ACTIVITY` |
| Late structure | 2024-12-31 includes hiring/capex/supplier-class signals |
| Non-decreasing best | Late best overall ≥ early best overall |
| Independence | Full package `independent_source_count` < `raw_source_count` (family + wire reprint) |

## Not proven

- Real-world early discovery of iron-air storage as an industry
- Accuracy of entity resolution on messy assignee strings
- Quality of automatic claim extraction from patents/news (claims are pre-labeled)
- Calibration of absolute score thresholds on live corpora
- Any market or trading implication

## Design intent

This case is a **contract test for time** and **honesty of status under sparse early evidence**, not a leaderboard of industry-finding accuracy.

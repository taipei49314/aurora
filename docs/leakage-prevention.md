# Temporal Leakage Prevention (spec §19, §20)

## Cutoff semantics
`leakage.apply_cutoff(observations, sources, cutoff)` returns only data with
`observed_at ≤ cutoff`. Observations with **missing dates are excluded** from a
cutoff run (we cannot prove they belong to the past) and counted separately.
Sources are restricted to those published on/before the cutoff (undated sources
kept only if referenced by an included observation).

## Hard guard
`leakage.assert_no_leakage(observations, cutoff)` re-scans the *included* set and
raises `FUTURE_DATA_LEAKAGE` (structured error, with entity/source ids and dates)
if anything dated after the cutoff — or undated — slipped through. The pipeline
calls this after applying the cutoff, and the backtest calls it for every cutoff.

## What a cutoff run must NOT use (spec §19)
- future observations — excluded by date.
- future taxonomy — the taxonomy is **versioned** (`taxonomy_version`) and the
  run records which version it used; a historical run pins an era-appropriate
  version.
- future aliases / labels / cluster results — the engine never reads
  `tests/ground_truth/` (enforced by
  `test_errors_isolation.py::test_engine_source_never_reads_ground_truth`), and
  feature statistics are computed only from the cutoff subset, not the full
  corpus.

## Manifest
Every cutoff run reports `cutoff_date`, `included_observation_count`,
`excluded_future_observation_count`, `excluded_undated_observation_count`.

## Evidence
`make backtest` over six cutoffs discovers the three real latent industries
~3.5 years early with **future_leakage_violations = 0** and **0 false-positive
candidates**; hype clusters stay hype at every cutoff and the failed cluster
downgrades EMERGING→REJECTED as counterevidence arrives.

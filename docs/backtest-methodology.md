# Historical Backtest Methodology (spec §20)

## Purpose and source of truth

The historical backtest repeatedly runs the same deterministic discovery
pipeline at ordered cutoff dates, tracks the resulting clusters, and reports
internal early-detection and reversal metrics. The executable definition is
`backend/aurora/backtest.py`; cutoff enforcement is in
`backend/aurora/leakage.py` and is documented separately in
`leakage-prevention.md`.

This is a replay of the supplied corpus, not a market-return backtest and not an
external proof that an industry existed. Its reference outcome is AURORA's own
full-data classification on the same snapshot.

## Inputs

`run_backtest(snapshot, taxonomy, cutoffs, cfg)` receives:

- one imported `Snapshot`, treated as read-only by the replay pipeline;
- one loaded `Taxonomy` object;
- cutoff strings expected to be ISO dates; and
- one `EngineConfig`, defaulting to `DEFAULT_CONFIG`.

Cutoffs are sorted before use. Every cutoff run and the full-data reference run
use the same snapshot, taxonomy object and engine configuration. Invalid dates
are rejected by `leakage.parse_cutoff` through the normal pipeline error model.

## Replay procedure and boundaries

For every cutoff:

1. Call `run_pipeline(..., cutoff_date=cutoff)`. The pipeline includes only
   observations whose event date and source publication date are on or before
   the cutoff, then calls the hard leakage assertion.
2. Apply the cutoff and hard assertion again inside `run_backtest`. A leakage
   violation raises `FUTURE_DATA_LEAKAGE`; the backtest does not continue with a
   partially contaminated result.
3. Retain each historical hypothesis's entity-id set, status, generated name
   and overall score for matching.

After the cutoff sweep, run the pipeline once with `cutoff_date=None`. Each
full-data hypothesis defines one track. At every cutoff, choose the historical
cluster with the largest entity-set Jaccard similarity:

```text
Jaccard(final, historical) = |final entities ∩ historical entities|
                              / |final entities ∪ historical entities|
```

The historical cluster is accepted as the same latent field only when Jaccard
is at least `0.4`; otherwise that track's status at the cutoff is `ABSENT`.
Matching does not use generated names or current industry labels.

For each track:

- `first_emerging_cutoff` is the first matched cutoff whose status is
  `EMERGING_CAPABILITY_CLUSTER` or `INDUSTRY_CANDIDATE`;
- `first_candidate_cutoff` is the first matched cutoff whose status is exactly
  `INDUSTRY_CANDIDATE`; and
- `early_discovery_lead_days` is calculated only for a final
  `INDUSTRY_CANDIDATE`, from its first emerging cutoff to the last supplied
  cutoff.

The aggregate median sorts non-zero lead-day values and selects the element at
`len(values) // 2`. For an even number of values this is the upper middle value,
not the arithmetic mean of the two middle values.

`false_positive_candidates` contains tracked clusters that were a candidate at
some cutoff but finish as `HYPE_CLUSTER`, `REJECTED`, or
`INSUFFICIENT_EVIDENCE`. That is an internal status reversal definition; it is
not a real-world false-positive rate.

## Outputs and provenance

The returned dictionary contains:

- the sorted `cutoffs`;
- one track per full-data hypothesis, including final status/name/score, the
  cutoff/status/overall history, both first-detection cutoffs and lead days;
- `median_early_discovery_lead_days`;
- `false_positive_candidates`; and
- `future_leakage_violations`, which is `0` for a completed result because a
  detected violation raises before return.

Every internal cutoff `ResearchRun` records its snapshot id, cutoff, engine,
feature and taxonomy versions, scoring and algorithm configuration, input and
result manifest hashes, and a leakage manifest. The current
`run_backtest` return value does not include those `ResearchRun` objects or the
per-cutoff leakage manifests; it exposes only the compact track history and the
aggregate zero-violation field. `scripts/run_backtest.py` prints that compact
result, and `POST /api/backtests` stores and returns the same dictionary in the
process-local API repository.

## Interpretation limits

- The full-data run is an internal reference, not ground truth. Status accuracy
  against Northstar labels is evaluated separately under `tests/`; runtime
  backtesting does not read those labels.
- Tracks are created only for hypotheses present in the full-data run. A
  historical cluster that disappears without a match to any final hypothesis is
  not represented as its own track and therefore cannot enter the current
  false-positive list.
- The reversal list does not count final `DORMANT`,
  `EXISTING_INDUSTRY_VARIANT`, or `EMERGING_CAPABILITY_CLUSTER` statuses as
  false positives.
- Lead time ends at the last requested cutoff, not at an independently observed
  market-recognition date. Changing the cutoff grid can change both the first
  detection and the reported lead time.
- Cluster matching retains only the best match and the `0.4` boundary. The
  returned history does not record the matched hypothesis id, entity set or
  Jaccard value, so split/merge details require rerunning or extending the
  diagnostic output.
- The same taxonomy object is reused at every cutoff. Version metadata is
  recorded on runs, but `run_backtest` does not select an era-specific taxonomy
  or verify that taxonomy content was public at the cutoff; callers must provide
  an appropriate taxonomy when that distinction matters.
- Input omissions, incorrect dates, optimistic reliability labels and incorrect
  independence groups remain corpus-quality problems. The cutoff guard prevents
  future-dated rows from entering; it does not verify that the supplied facts are
  true.

## Verification

- `tests/test_leakage_backtest.py::test_backtest_reports_no_leakage_and_tracks`
  checks track creation, the zero-violation contract and the current internal
  reversal behavior.
- `tests/test_leakage_backtest.py::test_backtest_detects_industries_before_full_run`
  requires at least one final candidate to have an earlier emerging cutoff.
- The remaining tests in `tests/test_leakage_backtest.py` cover cutoff boundaries,
  invalid dates, missing or future source publication dates, and the hard
  leakage assertion.
- `tests/test_errors_isolation.py::test_engine_source_never_reads_ground_truth`
  enforces the test-label boundary for engine modules.
- `make backtest` or `python scripts/run_backtest.py` runs the six-cutoff
  Northstar demonstration; its measured values describe that synthetic corpus
  and cutoff grid only.

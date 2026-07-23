# Case: patentsview-sample (Loop 4A)

Offline **PatentsView-compatible** patent dump → AURORA package.

## Honesty

- Default `dump.json` is a **CI fixture** in PatentsView field layout (synthetic content).
- The adapter accepts a **real PatentsView / bulk export** of the same shape with **no code changes**.
- This case proves **ingest path + independence + cutoff leakage**, not real-world industry discovery.
- Not investment advice.

## Reproduce

```bash
# from repo root
python -m adapters patentsview cases/patentsview-sample/dump.json \
  -o cases/patentsview-sample/package.json --strip --validate --strict

PYTHONPATH=backend python scripts/check_case_scorecard.py cases/patentsview-sample

# or
make patentsview-sample
```

## Replace with a real dump

1. Export patents as JSON with a top-level `patents` (or `results`) array.
2. Overwrite `cases/patentsview-sample/dump.json` (keep a copy of the fixture if needed).
3. Re-run `make patentsview-sample`.
4. Update this README’s honesty section to name the real source and date accessed.

## Scorecard gates

See `scorecard.json`:

- import_errors = 0
- has `PATENT_ACTIVITY`
- independent_source_count < raw_source_count (shared family)
- min 4 sources in the default fixture

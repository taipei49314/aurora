# Case: iron-air-retro (Loop 3)

Public-style **retro cutoff spine** for AURORA.

## Honesty (read first)

- Package is **hand-curated offline fiction**, not scraped USPTO/news dumps.
- Inspired by public long-duration storage themes only.
- Measures **engine temporal behavior** (leakage, early vs late signal), **not** real-world discovery lead time.
- Not investment advice. No BUY/SELL outputs.

## Reproduce

```bash
PYTHONPATH=backend python scripts/run_retro_case.py cases/iron-air-retro
# or
make retro-case
```

## Cutoffs

| Cutoff | Intent |
|--------|--------|
| `2020-12-31` | Seed only (paper + narrative hype) — must not look like a solid industry candidate |
| `2022-12-31` | Formation (patents) — real investment types present |
| `2024-12-31` | Hiring / capex / supply / standards — stronger than 2020 |

Gates live in `ledger.json`. Latest machine report: `last_run.json` (generated).

## Files

| File | Role |
|------|------|
| `package.json` | Import package (entities/sources/observations) |
| `ledger.json` | Expected temporal gates + honesty statements |
| `last_run.json` | Last `run_retro_case` report (gitignored) |
| `scorecard.md` | Human summary of what is / is not proven |

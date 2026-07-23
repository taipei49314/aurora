# Contributing to AURORA

Thanks for helping make research tools more honest.

## What fits

- Deterministic pipeline improvements with tests
- Offline adapters for public data formats (no silent network calls)
- Documentation, cases, and scorecards that state what is **not** proven
- Bug fixes, leakage checks, import-schema clarifications

## What does not fit (without a design discussion)

- Runtime LLM classification of industries
- BUY/SELL, target prices, or broker integrations
- Scrapers that invent claims not present in source text
- Breaking determinism (unordered sets, unseeded RNG, non-replayable IDs)

## Development

```bash
# Python 3.9+ (3.11+ preferred)
python -m pip install -r backend/requirements.txt
export PYTHONPATH=backend   # Windows: $env:PYTHONPATH = "backend"

python -m pytest tests/ -q
make demo                   # or: PYTHONPATH=backend python backend/aurora/cli.py
```

Useful checks:

```bash
make validate-example
make retro-case
make patentsview-sample
```

## Code expectations

1. **Tests** for behavior changes (unit or integration).
2. **Self-audit honesty** — if something is partial, say so in docs, not only in chat.
3. **Import contract** — keep `docs/import-schema.md` and examples in sync when changing package shape.
4. **No secrets** in fixtures; use `.example` domains and synthetic IDs.

## Pull requests

- Small, focused diffs beat mega-PRs.
- Describe *why* and how you verified (commands + expected outcome).
- Link any issue or case (`cases/…`) you exercised.

## Code of conduct

Be precise, kind, and evidence-oriented. Disagree with claims, not people.

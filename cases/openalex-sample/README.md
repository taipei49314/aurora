# Case: openalex-sample

Offline OpenAlex-shaped works → AURORA package.

```bash
python -m adapters openalex adapters/fixtures/openalex_sample.json \
  -o cases/openalex-sample/package.json --strip --validate --strict
PYTHONPATH=backend python scripts/check_case_scorecard.py cases/openalex-sample
```

Honesty: fixture is synthetic; swap for a real OpenAlex works export.

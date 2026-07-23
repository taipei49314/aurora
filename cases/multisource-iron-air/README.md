# Case: multisource-iron-air

PatentsView-compatible patents + jobs + news, joined with **shared LEI/domain
`external_ids`**, then engine-imported so name variants collapse.

## Build

```bash
python scripts/build_multisource_case.py
PYTHONPATH=backend python scripts/check_case_scorecard.py cases/multisource-iron-air
PYTHONPATH=backend python scripts/resolve_entities.py cases/multisource-iron-air/package.json \\
  --ref "ext:lei:LEI-FERRO-DEMO" --list-external
```

Or: `make multisource-case`

## Honesty

- Offline fixtures only
- Demo LEI ids (`LEI-*-DEMO`) are **join keys**, not real LEI registry values

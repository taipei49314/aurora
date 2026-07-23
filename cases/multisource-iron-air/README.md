# Case: multisource-iron-air

Five offline adapters, one package, companies joined by **LEI/domain**:

| Adapter | Signal |
|---------|--------|
| patentsview | `PATENT_ACTIVITY` |
| jobs | `HIRING_ACTIVITY` |
| news | `SUPPLIER_RELATIONSHIP` (+ wire reprint) |
| filings | `CAPEX_ACTIVITY` / tier **A** |
| openalex | `RESEARCH_ACTIVITY` |

## Build

```bash
python scripts/build_multisource_case.py
PYTHONPATH=backend python scripts/check_case_scorecard.py cases/multisource-iron-air
# or
make multisource-case
```

## Resolve demo

```bash
PYTHONPATH=backend python scripts/resolve_entities.py cases/multisource-iron-air/package.json \
  --ref "ext:lei:LEI-FERRO-DEMO"
```

## Honesty

Synthetic fixtures + demo LEI keys. Not real-world discovery proof.

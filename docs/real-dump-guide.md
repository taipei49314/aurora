# Bringing a real PatentsView (or bulk) dump

AURORA never crawls. You supply offline JSON; adapters convert it.

## 1. Get a dump

Any export with a top-level `patents` or `results` array and PatentsView-like
fields works:

- `patent_number` / `patent_id`
- `patent_title` / `title`
- `patent_abstract` / `abstract`
- `patent_date`, `app_date`
- `assignees[]` with `assignee_organization`
- `cpcs[]` with `cpc_subgroup_id`
- optional `patent_family_id`

Save as e.g. `cases/patentsview-sample/dump.json` (replace the CI fixture).

## 2. Convert + validate

```bash
python -m adapters patentsview path/to/dump.json \
  -o cases/patentsview-sample/package.json --strip --validate --strict

PYTHONPATH=backend python scripts/check_case_scorecard.py cases/patentsview-sample
```

## 3. Join with other sources via external_ids

Stamp stable ids on companies (LEI, domain, CIK) in the package or upstream:

```json
{
  "entity_type": "COMPANY",
  "canonical_name": "Example Corp",
  "external_ids": [
    {"system": "lei", "id": "…"},
    {"system": "domain", "id": "example.com"}
  ]
}
```

Then merge packages:

```bash
python -m adapters merge patents.json jobs.json news.json -o combined.json --strip --validate
```

Engine import **merges** entity rows that share the same external id.

## 4. Dry-run resolution

```bash
PYTHONPATH=backend python scripts/resolve_entities.py combined.json \
  --list-external
PYTHONPATH=backend python scripts/resolve_entities.py combined.json \
  --ref "ext:lei:…"
```

Or API (with server running):

```http
POST /api/resolve
{"ref": "ext:lei:…"}
```

## Honesty checklist

- [ ] Document source URL / bulk name / access date in the case README
- [ ] Do not claim industry discovery without a cutoff ledger + public methodology
- [ ] Respect redistribution license of the dump
- [ ] Prefer synthetic LEI only in demos (`LEI-*-DEMO`); real dumps use real ids

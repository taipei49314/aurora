# Bringing a real PatentsView dump

AURORA never crawls. Supply offline JSON, or use a separate extraction step to
join an official relational bulk product into adapter-ready JSON.

## 1. Choose the source shape

The `patentsview` adapter accepts a top-level `patents` or `results` array and
current/legacy PatentsView fields, including:

- `patent_number` / `patent_id`, title, abstract, and grant date;
- `patent_earliest_application_date` or nested `application.filing_date`;
- nested `assignees[]`, `inventors[]`, `cpc_current[]`, or `cpc_at_issue[]`;
- optional auditable `patent_family_id` (never synthesize one).

Official bulk downloads are TSV tables, not this JSON shape. Use
`scripts/extract_patentsview_case.py` as the reference for checksum validation,
streaming joins, fixed record selection, and deterministic serialization.

## 2. Bind the vendored artifact to lineage

Place `corpus-manifest.json` beside the JSON input. The manifest must name the
dataset id/version, origin URL, license, timezone-qualified retrieval timestamp,
and every vendored artifact's relative path, byte count, and SHA-256. The
PatentsView CLI automatically validates a sibling manifest before conversion.

The real sample also records official upstream byte counts/MD5s, selection IDs
and commit-pinned selection sources. Its extractor regenerates both the vendored
dump and manifest from the uncommitted official archives.

## 3. Convert and validate

```bash
python -m adapters patentsview path/to/dump.json \
  --lineage-manifest path/to/corpus-manifest.json \
  -o path/to/package.json --strip --validate --strict

PYTHONPATH=backend python scripts/lint_package.py path/to/package.json \
  --strict --require-documents --no-provisional --public-corpus
```

`--strip` keeps package defaults and compact lineage while omitting adapter
diagnostics. The manifest digest and artifact digest are stamped into every
output row, and explicit source acquisition timestamps survive engine import.

## 4. Join with other sources via external_ids

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
python -m adapters merge patents.json jobs.json news.json \
  -o combined.json --strip --validate
```

Engine import merges entity rows that share an external id. Distinct corpus
lineages are retained in a deterministically sorted package envelope.

## 5. Dry-run resolution

```bash
PYTHONPATH=backend python scripts/resolve_entities.py combined.json --list-external
PYTHONPATH=backend python scripts/resolve_entities.py combined.json --ref "ext:lei:…"
```

## Honesty checklist

- [ ] Record source/product URL, release, retrieval time, license and attribution.
- [ ] Record full artifact SHA-256 separately from row-level content hashes.
- [ ] Keep API keys, login cookies and large upstream products out of the repo.
- [ ] Do not invent family, assignee, inventor, abstract or ontology fields.
- [ ] State transformations and that PatentsView research data are not the
  official USPTO record.
- [ ] Do not claim discovery performance from a small adapter sample.
- [ ] Run the public-corpus, document, span and provisional-entity gates.

# Case: patentsview-sample

Five real granted-patent metadata records from the USPTO PatentsView final 2024
archive, joined offline and converted into an AURORA package.

## Provenance and honesty

- Upstream: USPTO, *Final release of PatentsView metadata, pre-grant and
  granted (12/31/2024)*, DOI `10.5281/zenodo.15058362`.
- License: `CC-BY-4.0`; attribution and all upstream checksums are recorded in
  `corpus-manifest.json`.
- Selection: three IDs from the commit-pinned PatentSearch API example and two
  from its commit-pinned validation data. This is an adapter integration sample,
  not a topical sample and not evidence of industry discovery performance.
- PatentsView is research data, not the official USPTO record. Changes were made
  when the three TSV tables were joined and serialized as JSON.
- The selected tables contain no patent-family field. Aurora therefore treats
  all five patents as independent; no family relationship is invented to pass a
  scorecard.

## Rebuild the vendored snapshot

Download the three artifacts named in `corpus-manifest.json` into
`.tmp/patentsview-2024/`, then run:

```bash
python scripts/extract_patentsview_case.py \
  --input-dir .tmp/patentsview-2024 \
  --case-dir cases/patentsview-sample
```

The extractor verifies every official byte count and MD5, joins only the five
declared `patent_id` values, emits LF-stable JSON, and records the resulting
`dump.json` SHA-256. The large upstream files are never committed.

## Convert and verify

```bash
python -m adapters patentsview cases/patentsview-sample/dump.json \
  -o cases/patentsview-sample/package.json --strip --validate --strict

PYTHONPATH=backend python scripts/check_case_scorecard.py cases/patentsview-sample
PYTHONPATH=backend python scripts/lint_package.py \
  cases/patentsview-sample/package.json --strict --require-documents \
  --min-char-span-ratio 1.0 --no-provisional --public-corpus
```

When `corpus-manifest.json` sits beside the input, the adapter validates the
artifact and stamps its canonical manifest SHA-256 into package lineage and
every entity, source, observation, and document.

## Scorecard

The committed case requires zero import errors, five sources/documents, five
independent sources, `PATENT_ACTIVITY`, 100% observation spans, no provisional
entities, an exact digest-bound corpus lineage match, and equality with a fresh
deterministic conversion of `dump.json`. The full gate also rebuilds to `.tmp`
and byte-compares the LF-stable package so stale or hand-edited output fails.

# Good first issues (for maintainers to open)

Copy into GitHub issues when seeking contributors.

## 1. Real PatentsView dump smoke

Replace `cases/patentsview-sample/dump.json` with a small real export (respect license), update case README with source + date, run `make patentsview-sample`.

## 2. Adapter: OpenAlex paper dump — **done (v0.1.4)**

Offline JSON → `PAPER` sources + `RESEARCH_ACTIVITY` observations; fixture + tests; document fields in `docs/import-schema.md`.

## 3. Data Explorer: show reliability_tier filter — **done (v0.1.5)**

Filter sources table by A/B/C/D; link to data_quality explanation in docs.
API: `GET /api/sources?reliability_tier=`.

## 4. CLI: `python -m adapters doctor` — **done (v0.1.3)**

Print adapter list, fixture paths, and one-line convert smoke for each fixture.

## 5. Document Chinese UI strings policy — **done (v0.1.5)**

README **Language policy**: engine English-first; case honesty bilingual optional.

## 6. Schema: first-class `family_id` — **done (v0.1.8)**

`Source.family_id` on import (top-level or metadata), export, stats coverage,
Data Explorer column; USPTO adapter emits top-level `family_id`.

## 7. Dual dates: first-class `event_date` — **done (v0.1.10)**

`Source.event_date` (app/filing) alongside `published_at` (grant/pub); metadata
fallback; empty observation `observed_at` falls back to event_date; USPTO
adapter emits top-level; Dashboard + stats coverage.

## 8. Schema: first-class `event_id` — **done (v0.1.11)**

`Source.event_id` + `Observation.event_id`; shared event_id collapses source
independence; obs inherits from source; adapters emit top-level; stats/UI.

## 9. First-class `outlet_domain` / `wire_id` — **done (v0.1.12)**

Source fields for outlet identity; independence derive `wire:` / `domain:`;
adapters emit top-level; stats + Data Explorer columns.

## 10. First-class geo / jurisdiction — **done (v0.1.13)**

`Source.geo` + `Observation.geo` (country/region/city/jurisdiction/raw);
jobs adapter emits top-level geo; stats country histograms; Data Explorer column.

## 11. License first-class + public-corpus lint — **done (v0.1.14)**

`Source.license` (metadata + package default); stats/UI; USPTO/OpenAlex emit
license; `lint_package --public-corpus` / `--require-license`.

## 12. Full document + span — **done (v0.1.15)**

`Observation.document_id` + `char_span`; optional package `documents[]`;
API `/api/documents`; adapters emit top-level `document_id`.

## 13. PERSON entity type + document highlight UI — **done (v0.1.16)**

Optional `PERSON` type (not industry-clusterable); patent adapters emit inventors;
Data Explorer observation detail loads document text and highlights `char_span`.

## 14. OpenAlex authors → PERSON + entity_type chips — **done (v0.1.17)**

OpenAlex adapter emits PERSON from authorships (orcid/openalex_author ids);
`GET /api/entities?entity_type=`; Data Explorer entity_type chips from stats.

## 15. Documents tab in Data Explorer — **done (v0.1.18)**

Documents tab with stubs from observation.document_id; linked observations via
`?document_id=`; stats `document_ids_referenced`.

## 16. Auto-build documents[] from source excerpts — **done (v0.1.19)**

Adapters call `ensure_documents` so packages include full `documents[]` rows
built from source title/excerpt/url/license (`document_id` == `source.ref`).
`strip_package` / `merge_packages` preserve and merge documents.

## 17. char_span auto-align — **done (v0.1.20)**

When `char_span` is missing but `document_id` + `text_excerpt` and document
text are present, locate the excerpt (exact → casefold → whitespace-flexible)
and set `[start, end]` with `metadata.char_span_auto`. Engine import + adapters.

## 18. Data Explorer auto-span badge + filters — **done (v0.1.21)**

Yellow **auto** badge on char_span column and observation detail; filter chips
All / with span / auto / no span. API: `?has_char_span=` and `?char_span_auto=`.

## 19. lint_package --require-documents — **done (v0.1.22)**

Fail when observation.document_id has no matching documents[] row. Soft stats
always (orphan_document_ids). Multisource check_all uses the hard flag.

## 20. Cases ship documents[] — **done (v0.1.23)**

Regenerated iron-air-mini / openalex / patentsview via adapters; retro stamped
document_id + ensure_documents. Scorecard gates `min_documents` +
`require_no_orphan_document_ids`. check_all lints all packages hard.

## 21. Progressive char_span + retro full coverage — **done (v0.1.24)**

align_char_span adds progressive word/char prefix match. Curated packages may
`append_unmatched` excerpts into document text. iron-air-retro: 21/21 spans.

## 22. Scorecard char_span floors — **done (v0.1.25)**

Gates `min_observations_with_char_span` and `min_char_span_ratio` on all cases;
iron-air-retro gains scorecard.json; check_all runs mini + retro scorecards.

## 23. lint_package char_span policy — **done (v0.1.26)**

`--require-char-spans` (document_id rows must have spans) and
`--min-char-span-ratio R`. Soft fields always reported. check_all wired.

## 24. Dashboard provenance quality panel — **done (v0.1.27)**

Coverage bars for document_id link, char_span, documents-with-text; stats
ratios for ratios and missing spans on document_id observations.

## 25. Data Explorer missing-on-doc filter — **done (v0.1.28)**

Chip + API ?missing_char_span=true for observations with document_id but no
char_span; also ?has_document_id=.

## 26. Dashboard → Data Explorer deep-links — **done (v0.1.29)**

Data Explorer filter state in URL (`tab`, `span`, `tier`, types, `q`);
Provenance quality panel links to missing-on-doc / observations / documents.

## 27. has_document_id chips + open document — **done (v0.1.30)**

Observations chips All / with doc / no doc (`?has_document_id=`); observation
detail links `document_id` into documents tab; Dashboard document_id bar deep-link.

## 28. Table document_id + StatCard deep-links — **done (v0.1.31)**

Observations table `document_id` cell → documents tab; Dashboard coverage
StatCards link into Data Explorer tabs (entities/sources/observations/documents).

## 29. Engine-only test path on Windows — **done (v0.1.32)**

`requirements-engine-test.txt` + `scripts/check_engine.py` so contributors without
MSVC/greenlet can still run demo + non-SQL tests.

## 30. Hypothesis table → Explorer deep-link — **done (v0.1.32)**

Dashboard hypothesis name links to `/hypotheses?id=`; Explorer opens that card,
scrolls into view, and keeps expand/collapse in the shareable URL.

## 31. Status chips → Explorer `?status=` filter — **done (v0.1.33)**

Dashboard status count cards link to `/hypotheses?status=`; Explorer has All /
per-status chips with shareable URL (composes with `?id=`).

## 32. Table Status badge dual deep-link — **done (v0.1.34)**

Dashboard table Status badge and name open Explorer with
`?status=<STATUS>&id=<hypothesis_id>` (filtered list + open card).

## Suggested next issues

- Wire real PatentsView dump into `cases/patentsview-sample` (human data)
- Enable GitHub Actions with a `workflow`-scoped PAT (human)
- `subject_raw` staging field for unresolved entity mentions
- DiscoveryMap / Timeline hypothesis picker → shareable `?id=` URL

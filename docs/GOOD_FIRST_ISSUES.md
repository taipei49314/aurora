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

## Suggested next issues

- Wire real PatentsView dump into `cases/patentsview-sample` (human data)
- Enable GitHub Actions with a `workflow`-scoped PAT (human)
- Optional: char_span auto-align from text_excerpt against document text

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

## Suggested next issues

- Wire real PatentsView dump into `cases/patentsview-sample` (human data)
- Enable GitHub Actions with a `workflow`-scoped PAT (human)
- License field first-class / required for public corpora
- Full document + span (`documents[]`)

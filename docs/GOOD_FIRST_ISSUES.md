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

## Suggested next issues

- Wire real PatentsView dump into `cases/patentsview-sample` (human data)
- Schema: first-class `event_id` for event-level dedup
- Enable GitHub Actions with a `workflow`-scoped PAT (human)

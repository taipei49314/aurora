# Changelog

All notable changes to AURORA are documented here.

Format inspired by [Keep a Changelog](https://keepachangelog.com/).
Versioning follows [SemVer](https://semver.org/) for the engine package
(`backend/aurora`, `ENGINE_VERSION`).

## [0.1.28] — 2026-07-24

### Added

- `GET /api/observations?missing_char_span=` (document_id without span)
- `GET /api/observations?has_document_id=`
- Data Explorer chip **missing on doc** (provenance gap preset)
- Dashboard tip links to the filter

### Changed

- Engine / feature → **0.1.28**

## [0.1.27] — 2026-07-24

### Added

- Dashboard **Provenance quality** panel (document link / char_span / text bars)
- Stats: `char_span_ratio`, `document_link_ratio`, `observations_missing_char_span`,
  `documents_with_text`

### Changed

- Engine / feature → **0.1.27**

## [0.1.26] — 2026-07-24

### Added

- `lint_package --require-char-spans` — fail if document_id obs lack char_span
- `lint_package --min-char-span-ratio R` — fail if overall span ratio below R
- Soft lint fields: `char_span_ratio`, `observations_missing_char_span`
- check_all: retro/openalex hard spans; mini/multisource/patentsview ratio floors

### Changed

- Engine / feature → **0.1.26**

## [0.1.25] — 2026-07-24

### Added

- Scorecard gates: `min_observations_with_char_span`, `min_char_span_ratio`
- `check_case_scorecard` reports `spans=N/M (pct)`
- All case scorecards set span floors; iron-air-retro scorecard.json added
- check_all runs iron-air-mini + retro scorecards

### Changed

- Engine / feature → **0.1.25**

## [0.1.24] — 2026-07-24

### Added

- **Progressive char_span align** (word/char prefix) for near-prefix excerpts
- `align_observation_char_spans(append_unmatched=True)` appends unmatched
  excerpts into document body (demo/curated packages)
- iron-air-retro: **21/21** observations now have char_span (progressive + append)

### Changed

- Engine / feature → **0.1.24**

## [0.1.23] — 2026-07-24

### Added

- Regenerated case packages with `documents[]` + spans (iron-air-mini, openalex, patentsview)
- iron-air-retro: stamp `document_id` + `ensure_documents` (12 docs)
- Scorecard gates: `min_documents`, `require_no_orphan_document_ids`
- `check_case_scorecard` imports `documents[]` and enforces new gates
- `check_all` lints all major cases/examples with `--require-documents`

### Changed

- Engine / feature → **0.1.23**

## [0.1.22] — 2026-07-24

### Added

- `lint_package --require-documents` fails when `observation.document_id` has no `documents[]` row
- Lint report fields: documents totals, referenced/orphan ids, span counts (incl. auto)
- Lint imports `documents[]` (was previously dropped)
- `check_all` runs multisource lint with `--require-documents`
- `examples/real_mini_package.json` now includes auto-built `documents[]` for refs

### Changed

- Engine / feature → **0.1.22**

## [0.1.21] — 2026-07-24

### Added

- Data Explorer **auto** badge on char_span (table + observation detail + document highlight)
- Observation **char_span** filter chips: All / with span / auto / no span
- `GET /api/observations?has_char_span=` and `?char_span_auto=` filters

### Changed

- Engine / feature → **0.1.21**

## [0.1.20] — 2026-07-24

### Added

- **char_span auto-align**: locate `text_excerpt` in document text when span missing
  - Engine: `aurora.char_span.align_char_span` at import (`metadata.char_span_auto`)
  - Adapters: `align_observation_char_spans` via `ensure_documents`
  - Snapshot count `char_spans_auto_aligned`; stats `observations_with_char_span_auto`
  - Dashboard shows auto span count

### Changed

- Engine / feature → **0.1.20**
- Adapters package → 0.1.7

## [0.1.19] — 2026-07-24

### Added

- Adapters **auto-build `documents[]`** from source excerpts (`document_id` == `source.ref`)
- `adapters.package_util.ensure_documents` / `build_documents_from_sources`
- `strip_package` keeps `documents[]`; `merge_packages` merges documents by id
- `package_stats` reports `documents` / `documents_with_text`

### Changed

- Engine / feature → **0.1.19**
- Offline adapter versions → 0.1.1 (OpenAlex 0.1.2); adapters package 0.1.6
- Multisource case export includes documents + observation `document_id`

## [0.1.18] — 2026-07-24

### Added

- Data Explorer **documents** tab (list + detail + linked observations)
- `GET /api/documents?include_stubs=` — stubs from `observation.document_id` when no full row
- `GET /api/observations?document_id=` filter
- Stats: `document_ids_referenced`; Dashboard shows full vs referenced counts

### Changed

- Engine / feature → **0.1.18**

## [0.1.17] — 2026-07-24

### Added

- OpenAlex adapter emits **`PERSON`** entities from authorships (`openalex_author`, `orcid`)
- Author names stamped on institution research-activity metadata
- `GET /api/entities?entity_type=` (comma lists); stats `entity_type_counts`
- Data Explorer **entity_type** chips

### Changed

- Engine / feature → **0.1.17**
- OpenAlex adapter version → 0.1.1

## [0.1.16] — 2026-07-24

### Added

- Optional entity type **`PERSON`** (inventors/authors/founders; **not** industry-clusterable)
- USPTO + PatentsView adapters emit `PERSON` entities from inventor lists
- Data Explorer observation detail: load document via `/api/documents/{id}` and **highlight `char_span`**

### Changed

- Engine / feature → **0.1.16**
- Import-schema PERSON gap closed

## [0.1.15] — 2026-07-24

### Added

- First-class **`Observation.document_id`** and **`char_span`** (metadata fallback; `[start,end]` or `{start,end}`)
- Optional package **`documents[]`** (`Document` model: text/path, license, source link)
- `GET /api/documents` (+ `/{document_id}`); export includes documents when present
- Stats: `observations_with_document_id`, `observations_with_char_span`, `documents_total`
- Data Explorer document columns; Dashboard documents card
- Adapters (USPTO/news/jobs/filings/openalex) emit top-level `document_id`

### Changed

- Engine / feature → **0.1.15**
- Snapshot may carry `documents`; snapshot_id stable when documents empty

## [0.1.14] — 2026-07-24

### Added

- First-class **`Source.license`** (metadata + package-level default via `license` / `package.license` / `meta.license`)
- Stats: `sources_with_license`, `license_counts`
- Data Explorer license column; Dashboard license card
- `lint_package --require-license` / `--public-corpus` fails when any source lacks license
- USPTO / OpenAlex adapters emit top-level `license`
- Import-schema public-corpus license policy section

### Changed

- Engine / feature → **0.1.14**
- Import-schema license gap marked done

## [0.1.13] — 2026-07-24

### Added

- First-class **`geo`** on `Source` and `Observation` (`country` / `region` / `city` / `jurisdiction` / `raw`)
- Accepts `location` alias and top-level `country` / `jurisdiction` shorthands; obs inherits source geo
- Stats: `sources_with_geo`, `observations_with_geo`, `observation_country_counts`, `entities_with_country`
- Data Explorer geo column; Dashboard geo card
- Jobs adapter emits top-level `geo` on sources and observations

### Changed

- Engine / feature → **0.1.13**
- Import-schema geo/jurisdiction gap marked done

## [0.1.12] — 2026-07-24

### Added

- First-class **`Source.outlet_domain`** and **`Source.wire_id`** (metadata fallback)
- Stats: `sources_with_outlet_domain`, `sources_with_wire_id`
- Data Explorer columns + Dashboard outlet/wire card
- News / jobs / filings / USPTO adapters emit top-level outlet fields

### Changed

- Engine / feature → **0.1.12**
- Import-schema outlet auto-independence gap marked done

## [0.1.11] — 2026-07-24

### Added

- First-class **`event_id`** on `Source` and `Observation` (metadata fallback; obs inherits source)
- Dedup layer 2b: sources sharing `event_id` are not independent
- Empty independence_group may derive `event:<id>` (after wire/domain/family)
- Stats: `sources_with_event_id`, `observations_with_event_id`, `unique_event_ids`
- Data Explorer `event_id` column; Dashboard event coverage card
- USPTO / news / jobs / filings adapters emit top-level `event_id`

### Changed

- Engine / feature → **0.1.11**
- Import-schema event-level dedup gap marked done

## [0.1.10] — 2026-07-24

### Added

- First-class **`Source.event_date`** (application/filing) alongside `published_at` (grant/pub)
- Empty observation `observed_at` falls back to `source.event_date` then `published_at`
- `/api/stats.sources_with_event_date`; export includes `event_date`
- Data Explorer sources columns: `event_date`, `published_at`
- Dashboard cards for `family_id` and `event_date` coverage
- USPTO adapter emits top-level `event_date`

### Changed

- Engine / feature → **0.1.10**
- Import-schema dual-date gap marked done

## [0.1.9] — 2026-07-24

### Added

- Data Explorer **source_type** chips (from `/api/stats.source_type_counts`)
- `scripts/check_all.py` runs `lint_package` on example + multisource packages
- API test for `GET /api/sources?source_type=`

### Changed

- Engine / feature → **0.1.9**

## [0.1.8] — 2026-07-24

### Added

- First-class **`Source.family_id`** (import top-level or `metadata.family_id`; export + UI)
- `GET /api/sources?source_type=` filter; stats include `source_type_counts`, `sources_total`, `sources_with_family_id`
- Data Explorer sources table **family_id** column
- USPTO adapter emits top-level `family_id` on patent sources
- `scripts/lint_package.py` — structure + import + vocabulary lint
- Scheduler mode A restored (20m autonomous slices) for hands-off progress

### Changed

- Engine / feature → **0.1.8**
- Import-schema gap “Patent family” marked done; JSON Schema documents `family_id`

## [0.1.7] — 2026-07-24

### Added

- Multisource case stacks **five** adapters: patentsview + jobs + news + **filings** + **openalex**
- Scorecard requires CAPEX + RESEARCH_ACTIVITY as well as patent/hire/supplier

### Changed

- Engine → **0.1.7**

## [0.1.6] — 2026-07-24

### Added

- Data Explorer **observation_type** chips (from `/api/stats`)
- **Filings** offline adapter (`python -m adapters filings …`) + fixture/tests
- Session-only intensive mode (scheduler disabled)

### Changed

- Engine → **0.1.6**

## [0.1.5] — 2026-07-24

### Added

- `GET /api/stats` — external_ids coverage, reliability tier mix, obs type mix
- `GET /api/sources?reliability_tier=A|B|C|D` (comma lists) and optional `?q=`
- `GET /api/observations?observation_type=` and optional `?q=`
- Data Explorer **sources** tab: A–D tier chips, colored badges, detail pane,
  links to scoring-model / import-schema
- Dashboard corpus stat cards + data-quality (DQ) column on hypothesis table
- `cases/openalex-sample` + scorecard wired into `check_all`
- README **language policy** (engine English-first; bilingual case notes optional)

### Changed

- Engine / package → **0.1.5**

## [0.1.4] — 2026-07-24

### Added

- **OpenAlex** offline adapter (`python -m adapters openalex …`) + fixture/tests
- Data Explorer uses `GET /api/entities?q=` for server-side entity filter

### Changed

- Engine / package → **0.1.4**

## [0.1.3] — 2026-07-24

### Added

- GitHub Actions **CI template** (`docs/ci-github-actions.yml` → copy to `.github/workflows/ci.yml`; runs `scripts/check_all.py`)
- Issue templates + `docs/GOOD_FIRST_ISSUES.md`
- `python -m adapters doctor` fixture/smoke check
- `GET /api/entities?q=` server-side filter
- Frontend header shows **engine version** from `/api/health`

### Changed

- Engine / package version → **0.1.3**

## [0.1.2] — 2026-07-24

### Added

- **Entity resolution via `external_ids`**: `ext:system:id`, structured subject/object,
  and `subject_external_ids` disambiguation
- **Import merge** of entity rows that share the same external id (aliases union)
- Collision reporting: `EXTERNAL_ID_COLLISION`
- Adapters emit **first-class** `external_ids` (USPTO/jobs/news/PatentsView)
- `scripts/resolve_entities.py` dry-run CLI; `POST /api/resolve`
- Case `cases/multisource-iron-air` (patents+jobs+news joined by demo LEI)
- `scripts/build_multisource_case.py`, `make multisource-case`
- Data Explorer UI: `external_ids` column + detail pane; hypothesis data_quality bars
- Data Explorer **Resolve** bar wired to `POST /api/resolve`
- `docs/real-dump-guide.md` for real PatentsView / bulk drop-in
- `scripts/check_all.py` / `make check-all` local pre-push gate

### Changed

- Engine / package version → **0.1.2**

## [0.1.1] — 2026-07-24

### Added

- Offline **adapters**: USPTO-shaped, PatentsView-compatible, jobs, news, merge CLI
- **Import schema** docs, JSON Schema, `examples/`, `scripts/validate_package.py`
- **Cases**: `iron-air-mini`, `iron-air-retro` (cutoff ledger), `patentsview-sample`
- Retro runner `scripts/run_retro_case.py` and scorecard checks
- `Entity.external_ids` first-class field (metadata fallback still accepted)
- Import auto-derives `independence_group` from `wire_id` / `outlet_domain` / `family_id`
- `reliability_tier` contributes to `data_quality_penalty`; breakdown in `score_explanation`
- OSS packaging: MIT LICENSE, CONTRIBUTING, SECURITY, this changelog

### Changed

- Engine / feature version → **0.1.1** (scoring and import behavior)
- README oriented for external users and open-source release

### Honesty

- Default PatentsView dump is a **format-compatible CI fixture**, not a live API pull
- Retro case measures temporal engine behavior on curated data, not real-world discovery lead time

## [0.1.0] — 2026-07-23

### Added

- Core discovery engine (stdlib): import → cluster → hype → classify
- Northstar synthetic corpus, determinism tests, leakage / backtest
- FastAPI API + React frontend (8 pages)
- SQLite persistence path and self-audit docs

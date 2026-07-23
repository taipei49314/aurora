# Changelog

All notable changes to AURORA are documented here.

Format inspired by [Keep a Changelog](https://keepachangelog.com/).
Versioning follows [SemVer](https://semver.org/) for the engine package
(`backend/aurora`, `ENGINE_VERSION`).

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

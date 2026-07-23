# Changelog

All notable changes to AURORA are documented here.

Format inspired by [Keep a Changelog](https://keepachangelog.com/).
Versioning follows [SemVer](https://semver.org/) for the engine package
(`backend/aurora`, `ENGINE_VERSION`).

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

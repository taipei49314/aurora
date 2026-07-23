# Evolution loop (plan → execute → test → confirm → plan)

Living checklist for real-world AURORA evolution. Each loop is intentionally small.

## Loop 0 (done) — Import contract

- `docs/import-schema.md`
- `examples/real_mini_package.json` + JSON Schema + `scripts/validate_package.py`
- Tests: `tests/test_example_package.py`

## Loop 1 (done) — Offline USPTO adapter skeleton

**Shipped:** `adapters/uspto.py`, fixture, `make adapt-uspto`, `tests/test_adapters_uspto.py`

**Confirm:** 3 patents → import_errors=0, independent 2/3 (family share)

## Loop 2 (done) — Multi-source package merge path

**Plan:** jobs + news adapters, merge CLI, iron-air-mini case + scorecard

**Shipped:**

- `adapters/jobs.py`, `adapters/news.py`
- fixtures `jobs_sample.json`, `news_sample.json`
- `python -m adapters merge …`
- `cases/iron-air-mini/` + `scripts/check_case_scorecard.py`
- `make adapt-merge-demo`
- Tests: `tests/test_adapters_jobs_news_merge.py`

**Confirm (2026-07-24):**

- Jobs emit `HIRING_ACTIVITY`; news emit `SUPPLIER_RELATIONSHIP`
- Wire primary+reprint → independent 2/3 on news alone
- Merge uspto+jobs+news → 9 sources, independent < raw, import_errors=0
- Scorecard gates pass

## Loop 3 (done) — Retro case spine

**Shipped:**

- `cases/iron-air-retro/package.json` — multi-year curated timeline
- `ledger.json` — cutoff gates + honesty statements
- `scripts/run_retro_case.py` + `make retro-case`
- `scorecard.md` — proven vs not proven
- Tests: `tests/test_retro_case.py`

**Confirm (observed):**

| Cutoff | included | best | top status |
|--------|----------|------|------------|
| 2020-12-31 | 2 | ~8 | INSUFFICIENT_EVIDENCE (high hype) |
| 2022-12-31 | 8 | ~47 | EMERGING_CAPABILITY_CLUSTER |
| 2024-12-31 | 21 | ~54 | EMERGING_CAPABILITY_CLUSTER |
| leakage | 0 all cutoffs | | |

## Loop 4A (done) — PatentsView-compatible dump path

**Shipped:**

- `adapters/patentsview.py` — normalize PatentsView fields → `convert_uspto`
- Fixture + case `cases/patentsview-sample/` (`dump.json` replaceable by real export)
- `make patentsview-sample`, `tests/test_adapters_patentsview.py`

**Confirm:**

- 4 patents → import_errors=0, independent 3/4 (shared family)
- Cutoff 2020-12-31 leakage=0 with future exclusions > 0
- Scorecard gates pass

**Honesty:** default dump is format-compatible CI fixture; real export drops in without code changes.

## Loop 5 (done) — reliability_tier in data_quality_penalty

**Shipped (engine 0.1.1):**

- `_data_quality_penalty` / `_data_quality_assessment` use A–D tier costs (+0..15)
- Import stamps `metadata.reliability_tier` on observations
- Docs: scoring-model, import-schema; tests `test_data_quality_reliability.py`
- Retro + scenario suites green (scores shifted slightly; gates still hold)

## Loop 6 (done) — data_quality breakdown in score_explanation

- Hypothesis `score_explanation["data_quality"]` exposes tier_counts + factor penalties

## Loop 7 (done) — Entity.external_ids first-class

- `models.Entity.external_ids`, import merge, SQL fold/unfold, export API
- Tests: `test_entity_external_ids.py`

## Loop 8 (done) — import auto-independence

- Empty `independence_group` → derive `wire:` / `domain:` / `family:` from metadata
- Tests: `test_import_auto_independence.py`

## Loop 9 (done) — external_ids ER + import merge

- `EntityResolver` resolves `ext:system:id`, structured refs, ambiguous-name disambiguation
- Import merges entities sharing an external id; `EXTERNAL_ID_COLLISION` reported
- Engine **0.1.2**; tests `test_external_id_resolution.py`

## Loop 10 (done, local) — adapters external_ids + multisource case + resolve CLI/API

- Adapters first-class external_ids; merge util unions them
- `cases/multisource-iron-air` + `build_multisource_case.py`
- `scripts/resolve_entities.py`, `POST /api/resolve`

## Accumulated (not pushed yet)

Local commits include 0.1.2 ER + Loop 10 tooling. Push/tag when ready as **v0.1.2**.

## Loop 11 (done, local) — UI + dump guide + resolve API tests

- Data Explorer: external_ids column, filter, entity detail pane
- Hypothesis Explorer: data_quality penalty / factors
- `docs/real-dump-guide.md`
- API tests for `POST /api/resolve`

## Local backlog (still not pushed)

Commits ahead of `origin/master` for **v0.1.2** batch:

- ER external_ids + import merge
- Multisource case, resolve CLI/API
- Frontend external_ids + dump guide

## Loop 12 (done, local) — resolve UI + check-all

- Data Explorer Resolve bar → `POST /api/resolve`
- `scripts/check_all.py` / `make check-all` pre-push gate

## Loop 13 (done) — CI + doctor + autonomous push policy

- GitHub Actions CI, issue templates, adapters doctor, entities `?q=`, UI engine badge
- User authorized continuous push; releases tagged when a slice lands

## Loop 14 (next)

1. Real PatentsView dump (human data)
2. OpenAlex paper adapter (good first issue)
3. Optional: frontend uses `entities?q=` for filter

**Out of scope:** live crawl service, multi-tenant SaaS, stock outputs

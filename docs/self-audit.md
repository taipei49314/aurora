# AURORA Self-Audit (spec §33 Phase 8)

Honest status of every major requirement. Values: **PASS** / **PARTIAL** /
**NOT_IMPLEMENTED**. PASS means the stated requirement has implementation and
evidence; it does not erase the model and validation boundaries recorded below.

Scope note: the core discovery engine, data foundation, historical validation,
API, SQLite persistence and the **full 8-page frontend** are implemented, tested
and (where observable) browser-verified. The Northstar corpus now hits the
target scale (**199 entities / 3120 observations**), enabled by a MinHash-LSH
dedup path.

Run everything: `make test` (398 tests) · `make demo` · `make backtest` ·
`make benchmark` · `make api` + `make frontend`.
Test buckets: `pytest -m unit` (266) · `-m integration` (93) · `-m e2e` (14),
plus 25 unmarked support/contract tests.

| # | Requirement (spec §) | Status | Evidence file | Command / test |
|---|---|---|---|---|
| 1 | Local-first, offline, no external API/LLM at runtime | **PASS** | `backend/aurora/*` (pure stdlib core) | `make demo` runs with zero third-party runtime deps |
| 2 | Deterministic content/stable IDs + full manifests (§22) | **PASS** | `ids.py`, `importing.py`, `store.py`, `pipeline.py` | generated record ids are content-derived; stable row-set `snapshot_id` is paired with full-payload `input_manifest_hash`, which is included in `run_id`; 50-run determinism + persistence collision regressions |
| 3 | Core data model (§6) | **PASS** | `models.py` | imported by all tests |
| 4 | Import pipeline w/ layered stages (§7) | **PASS** | `importing.py` | `test_import_dedup.py` |
| 5 | Re-import idempotency (§34.3) | **PASS** | `importing.py` | `test_import_dedup.py::test_reimport_is_idempotent` |
| 6 | Structured per-row import errors (§7,§27) | **PASS** | `errors.py`, `importing.py` | `test_import_dedup.py::test_schema_error_reported_with_context` |
| 7 | Source dedup + independence (exact/declared/near) (§8) | **PASS** | `dedup.py` | `test_import_dedup.py` (5 tests) |
| 8 | Independent < raw source count used in scoring (§8) | **PASS** | `dedup.py`, `pipeline.py` | `test_import_dedup.py::test_independent_less_than_raw...` |
| 9 | Entity resolution + rename + ambiguity (§7) | **PASS** | `entity_resolution.py` | `test_entity_resolution.py` (5 tests) |
| 10 | Deterministic feature construction, no keyword list (§9) | **PASS** | `features.py` | `test_properties.py`, `test_clustering.py` |
| 11 | Two clustering methods, comparable (§11) | **PASS** | `clustering.py`, `graph.py` | `test_clustering.py::test_two_methods_are_comparable` |
| 12 | Distinct industries don't chain-merge (§11) | **PASS** | `features.py` (fix), `clustering.py` | `test_clustering.py::test_distinct_industries_do_not_chain` |
| 13 | Cluster stability / bootstrap (§11) | **PASS** | `clustering.py` | `test_clustering.py::test_stability_*` |
| 14 | Existing-taxonomy comparison (§12) | **PASS** | `taxonomy.py`, `datasets/taxonomy/taxonomy.json` | `test_taxonomy_naming.py` |
| 15 | Naming-gap analysis (§13) | **PASS** | `naming_gap.py` | `test_scenarios.py::test_scenario_h...` |
| 16 | Transparent scoring formula (§14) | **PASS** | `scoring.py`, `config.py` | `test_scoring_determinism_divergence.py` (4 tests) |
| 17 | Hype filter (§15) | **PASS** | `hype.py` | `test_hype_counterevidence_bottleneck.py` |
| 18 | Counterevidence engine + downgrade (§16) | **PASS** | `counterevidence.py`, `classify.py` | `test_scenarios.py::test_scenario_f...` |
| 19 | Value-chain construction w/ evidence + inferred flag (§17) | **PASS** | `value_chain.py` | endpoint `/value-chain`; `test_scenarios` provenance |
| 20 | Bottleneck analysis (structural, not volume) (§18) | **PASS** | `bottleneck.py` (Brandes betweenness) | `test_scenarios.py::test_scenario_d...` |
| 21 | Temporal cutoff + leakage prevention (§19) | **PASS** | `leakage.py` | `test_leakage_backtest.py` cutoff/source-date contracts |
| 22 | Historical backtest + lead time (§20) | **PASS** | `backtest.py` | `make backtest`; `test_leakage_backtest.py` |
| 23 | First-divergence analysis (§21) | **PASS** | `divergence.py` | `test_scoring_determinism_divergence.py` (3 tests) |
| 24 | Insert-once Research Run w/ manifests (§22) | **PASS** | `store.py`, `pipeline.py` | read-only engine contract + insert-or-verify persistence; full input manifest participates in `run_id`; `test_determinism_50_runs`; per-run feature-space candidate diagnostics |
| 25 | Classification into all required statuses (§3) | **PASS** | `classify.py` | `test_scenarios.py`, `test_quality_groundtruth.py` |
| 26 | Synthetic Northstar corpus w/ archetypes (§23) | **PASS** | `datasets/northstar/generate.py` | 199 entities / 3120 obs (meets 180/3000); all 8 archetype families + reprints/contradictions/missing-dates/aliases + 64-company background noise |
| 27 | Ground-truth isolation from runtime (§23,§5.10) | **PASS** | `tests/ground_truth/` | `test_errors_isolation.py::test_engine_source_never_reads_ground_truth` |
| 28 | Acceptance Scenarios A–H (§24) | **PASS** | — | `test_scenarios.py` (all pass) |
| 29 | Determinism over 50 runs (§29) | **PASS** | `pipeline.py` | `test_determinism_50_runs` |
| 30 | Quality metrics vs ground truth (§30) | **PASS** | `test_quality_groundtruth.py` | precision ≥0.85, recall ≥0.80, status accuracy 100% |
| 31 | Provenance completeness 100% (§30) | **PASS** | `pipeline.py` | `test_errors_isolation.py::test_provenance_completeness...` |
| 32 | Benchmark + per-stage timing (§31) | **PASS** | `benchmarks/bench.py` | `make benchmark` (measured, not claimed) |
| 33 | Full API surface (§26) | **PASS** | `backend/api.py` | ~27 endpoints; `/imports` upload, `/exports` (raw-format round-trip), `POST /snapshots` (SQLite persist, idempotent) added 2026-07-23; `tests/test_api.py` now has 22 TestClient tests |
| 34 | Error model, no bare 500 (§27) | **PASS** | `errors.py`, `api.py` handler | bad cutoff → 422; `test_errors_isolation.py` |
| 35 | Frontend — all 8 pages (§25) | **PASS** | `frontend/src/pages/` | all 8 pages built, `tsc` clean, wired to API; 2026-07-23 the remaining 5 (Hypothesis Explorer, Timeline, Bottleneck Lab, Data Explorer, Run Comparison) were each driven live in a browser with zero console errors — every page now browser-verified |
| 36 | SQLite/SQLAlchemy persistence (§4) | **PASS** | `store_sql.py` | normalized snapshot tables, including complete document payloads, + runs; 28 persistence tests cover round-trip identity, same-id conflict rejection, legacy document backfill, migration-managed creation, and exact-current/exact-legacy/refuse adoption paths. Alembic builds all 6 tables, and a separate installed-wheel smoke verifies packaged migrations off-checkout |
| 37 | Docker compose one-command up (§4) | **PASS** | `docker-compose.yml`, Dockerfiles, `frontend/vite.config.ts`, `scripts/docker_audit.py` | static contract audit passes; 2026-08-21 runtime build/start and frontend-proxied `/api/health` verified with HTTP 200 |
| 38 | Test-count targets: 55 unit / 15 integ / 8 e2e (§28) | **PASS** | `tests/` (markers) | 398 tests: **266 unit / 93 integration / 14 e2e**, plus 25 unmarked support/contract tests. Select via `pytest -m <bucket>` |
| 39 | Phase 0 specification-audit docs (§33) | **PASS** | `docs/` | architecture, requirements matrix, import schema, 2 ADRs, and separate feature/clustering/scoring/hype/value-chain/counterevidence/bottleneck/leakage/backtest/threat-model docs |

## Known limitations / honest gaps
- **Windows without MSVC:** full `pip install sqlalchemy` may fail on greenlet
  wheels. Use `backend/requirements-engine-test.txt` + `python scripts/check_engine.py`
  (or `make check-engine`) for the engine-only gate — demo, version-sync, non-SQL
  pytest, validate-example, adapters doctor. API/persistence tests still need a
  full env with SQLAlchemy.
- **Source dedup near-dup** now uses **MinHash-LSH** (`dedup.py`), so it stays
  near-linear at 3120 sources (import+dedup+ER ≈ 1.0 s). Feature-space entity
  similarity uses the complete pair set below 1,000 clusterable entities, then
  switches to deterministic sparse blocking with oversized high-frequency
  blocks skipped; thresholds and realized candidate diagnostics are recorded in
  each Research Run manifest (engine 0.1.45), including accepted-block entity
  coverage and uncovered-entity counts.
- **Bottleneck substitutability** — FIXED 2026-07-23: an alternative now has to
  serve the same downstream via the same dependency type, so the co-listed
  component no longer counts and the shared supplier reads 0.0 (was 0.5).
  Regression-locked by `test_scenario_d_shared_supplier_has_no_false_substitutes`.
- **Frontend**: all 8 pages browser-verified live (last 5 done 2026-07-23,
  zero console errors; Run Comparison exercised end-to-end with a cutoff run).
- **Docker** compose build/start and the frontend-proxied `/api/health` path were
  verified on 2026-08-21. The static audit locks the host-local fallback and
  Compose service-DNS target, but should not replace a runtime smoke check after
  Docker or Vite configuration changes.
- **API**: `/imports` upload, `/exports` round-trip and `POST /snapshots`
  persistence shipped 2026-07-23; the API suite now has 22 TestClient tests.
- **Alembic**: wired 2026-07-23; the 2026-08-30 document-table migration and
  migration-managed creation, exact current/legacy adoption, and refusal paths
  are covered by the full CI dependency set. Configuration and revisions ship
  as package data, with an offline installed-wheel smoke outside the checkout.
- **Runtime note**: this machine's existing Python 3.9 environment can execute
  the whole suite, but the supported fresh API/full-test install is Python 3.10+
  because current safe `python-multipart` releases no longer support 3.9. The
  stdlib core remains supported on 3.9. Current local suite: 398 green
  (266 unit / 93 integration / 14 e2e / 25 unmarked).

## What is genuinely proven now (verified this session)
- All 9 archetypes classify exactly as their hidden ground truth at full scale
  (**199 entities / 3120 obs**); cluster precision ≥0.85, status accuracy 100%.
- **Determinism** holds over 50 runs (identical result hash) and **across the
  SQLite boundary** (round-tripped snapshot → identical result hash).
- A 6-cutoff backtest, **run live through the frontend**, discovers the three
  real industries ~3.5 years early (median lead 1277 d) with **0 future-leakage
  violations and 0 false positives**; the failed cluster downgrades
  EMERGING→REJECTED; hype clusters stay hype at every cutoff.
- The "quantum" hype cluster scores **11.7** — the engine does **not** inflate
  on buzzwords.
- **398 tests** green (266 unit / 93 integration / 14 e2e / 25 unmarked).

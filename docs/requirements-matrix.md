# Requirements Matrix (Phase 0, spec §33)

Maps each core requirement to the module that satisfies it and the test that
proves it. Detailed PASS/PARTIAL status lives in `self-audit.md`; this is the
design-time traceability map.

| Spec § | Requirement | Module | Test |
|---|---|---|---|
| §3 | Status vocabulary + gates | `classify.py` | `test_scenarios.py`, `test_quality_groundtruth.py` |
| §6 | Data model | `models.py` | (all) |
| §7 | Import pipeline layers | `importing.py` | `test_import_dedup.py` |
| §8 | Source independence | `dedup.py` | `test_import_dedup.py` |
| §9 | Deterministic features, no keyword list | `features.py` | `test_properties.py`, `test_clustering.py` |
| §10 | Staged pipeline (no monolith) | `pipeline.py` + modules | code review |
| §11 | Two clustering methods + stability | `clustering.py`, `graph.py` | `test_clustering.py` |
| §12 | Existing-taxonomy comparison | `taxonomy.py` | `test_taxonomy_naming.py` |
| §13 | Naming gap | `naming_gap.py` | `test_scenarios.py` (H) |
| §14 | Transparent scoring | `scoring.py`, `config.py` | `test_scoring_determinism_divergence.py` |
| §15 | Hype filter | `hype.py` | `test_hype_counterevidence_bottleneck.py` |
| §16 | Counterevidence + downgrade | `counterevidence.py`, `classify.py` | `test_scenarios.py` (F) |
| §17 | Value chain w/ evidence | `value_chain.py` | provenance tests |
| §18 | Bottleneck (structural) | `bottleneck.py` | `test_scenarios.py` (D) |
| §19 | Cutoff + leakage guard | `leakage.py` | `test_leakage_backtest.py` |
| §20 | Historical backtest | `backtest.py` | `test_leakage_backtest.py`, `make backtest` |
| §21 | First divergence | `divergence.py` | `test_scoring_determinism_divergence.py` |
| §22 | Immutable run + manifests | `store.py`, `pipeline.py` | determinism test |
| §23 | Northstar corpus + GT isolation | `datasets/northstar/generate.py` | `test_errors_isolation.py` |
| §24 | Scenarios A–H | (engine) | `test_scenarios.py` |
| §26 | API | `backend/api.py` | TestClient verification |
| §27 | Error model | `errors.py` | `test_errors_isolation.py` |
| §29 | Determinism (50×) | `pipeline.py` | `test_determinism_50_runs` |
| §30 | Quality metrics | (test) | `test_quality_groundtruth.py` |
| §31 | Benchmark | `benchmarks/bench.py` | `make benchmark` |

## Operational definition of an "unknown industry" (spec §3)
Turned into computable gates in `classify.py` + `scoring.py`:
- **cross-entity** → `n_entities ≥ 3`
- **cross-source** → `distinct_source_types ≥ 2` for candidacy
- **independent** → `independent_sources ≥ 3` (dedup-resolved groups)
- **novel** → taxonomy similarity below the existing-variant threshold
- **accelerating** → positive mean signal acceleration
- **value chain** → roles present ≥ threshold
- **real investment** → real-obs ratio saturating score
- **demand pull** → demand-obs ratio saturating score
- **naming gap** → high capability coherence + high name dispersion
- **falsifiable** → non-empty `disconfirmation_conditions` (required before
  `INDUSTRY_CANDIDATE`)

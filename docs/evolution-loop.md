# Evolution loop

## Operating mode

- **Current:** manual trigger. This file preserves the historical autonomous
  cycles; it is not evidence that a scheduler is still running.
- A session may prepare and verify focused local commits. Pushes and tags are
  explicit publication steps.
- GitHub Actions is live. `docs/ci-github-actions.yml` remains the reference copy.

## Shipped (through 0.1.49)

| Ver | Highlights |
|-----|------------|
| 0.1.1–0.1.4 | OSS, adapters base, ER external_ids, OpenAlex, resolve |
| 0.1.5 | stats API, tier filters, dashboard |
| 0.1.6 | obs-type chips, filings adapter |
| 0.1.7 | five-adapter multisource case |
| 0.1.8 | family_id first-class, source_type API filter, lint_package |
| 0.1.9 | source_type chips UI; lint wired into check_all |
| 0.1.10 | first-class `event_date` dual dates; dashboard coverage cards |
| 0.1.11 | first-class `event_id` event-level independence dedup |
| 0.1.12 | first-class `outlet_domain` / `wire_id` |
| 0.1.13 | first-class `geo` on Source + Observation |
| 0.1.14 | first-class `license` + public-corpus lint policy |
| 0.1.15 | `documents[]` + first-class `document_id` / `char_span` |
| 0.1.16 | `PERSON` entity type; document span highlight UI |
| 0.1.17 | OpenAlex authors → PERSON; entity_type API/UI chips |
| 0.1.18 | Data Explorer documents tab; document stubs + obs filter |
| 0.1.19 | Adapters auto-build `documents[]` from source excerpts |
| 0.1.20 | char_span auto-align from text_excerpt vs document text |
| 0.1.21 | Data Explorer auto-span badge + has_char_span API filters |
| 0.1.22 | lint_package `--require-documents` for orphan document_ids |
| 0.1.23 | All cases regenerated with documents[]; scorecard min_documents |
| 0.1.24 | Progressive char_span align; retro 21/21 spans |
| 0.1.25 | Scorecard min_observations_with_char_span / min_char_span_ratio |
| 0.1.26 | lint_package --require-char-spans / --min-char-span-ratio |
| 0.1.27 | Dashboard provenance quality panel + span ratio stats |
| 0.1.28 | Data Explorer missing-on-doc span filter + API |
| 0.1.29 | Dashboard quality deep-links + Data Explorer URL filters |
| 0.1.30 | has_document_id chips + observation→document deep-link |
| 0.1.31 | Table document_id links + Dashboard StatCard deep-links |
| 0.1.32 | Engine-only test gate; hypothesis row → Explorer `?id=` deep-link |
| 0.1.33 | Dashboard status chips → Explorer `?status=` filter |
| 0.1.34 | Table Status/name dual deep-link `?status=` + `?id=` |
| 0.1.35 | DiscoveryMap / Timeline shareable `?id=` picker |
| 0.1.36 | Explorer ↔ Map / Timeline cross-links with `?id=` |
| 0.1.37 | Bottleneck Lab cluster → Explorer deep-link |
| 0.1.38 | First-class `subject_raw` / `object_raw` mention staging |
| 0.1.39 | Opt-in provisional entities (`PROVISIONAL`, non-clusterable) |
| 0.1.40 | lint `--no-provisional` + resolve `--list-provisional` / `--promote` |
| 0.1.41 | Scorecard + check_all/engine forbid provisional on curated cases |
| 0.1.42 | Provisional visibility: API filters + Explorer chips + Dashboard |
| 0.1.43 | Adapter default raw mentions + deterministic entity-graph blocking |
| 0.1.44 | Per-run feature-space blocking diagnostics in research manifests |
| 0.1.45 | Per-run blocking diagnostics add accepted-block entity coverage |
| 0.1.46 | Offline Docker/Compose readiness audit; runtime was PARTIAL at release (verified 2026-08-21) |
| 0.1.47 | Manifest hash v2 (full input digest); Frontier Atlas mothership submit |
| 0.1.48 | Calendar-window hype fade; unit-safe bottleneck lead time; focused value-chain regressions |
| 0.1.49 | Real USPTO PatentsView sample; digest-bound corpus lineage; current API field fidelity |

## Next

1. Reference corpus/run digests from backtest outputs
2. Add a second independently licensed real corpus to exercise merged lineage

## Done

- **GitHub Actions CI enabled** (2026-07-26). `.github/workflows/ci.yml` runs
  `scripts/check_all.py` plus an engine-version sanity check on every push and PR
  to `master`/`main`. The account token now carries the `workflow` scope, so this
  is no longer human-blocked.
  The first run caught a real defect: `python-multipart` was never declared in
  `backend/requirements.txt`, so a clean install could not import the FastAPI app.
- **Docker Compose runtime verified** (2026-08-21). Both images built and
  started, the frontend-proxied `/api/health` returned HTTP 200, and the stack
  was removed cleanly. See `docs/docker-readiness.md` and PR #9.
- **Named Phase 0 model docs completed** (2026-08-30). Features, value chain,
  counterevidence, bottlenecks, backtesting, and threat boundaries now have
  separate code-grounded documents instead of architecture-only summaries.
- **Model semantic regressions completed** (v0.1.48). Hype fade uses cutoff-
  anchored calendar windows, bottleneck lead time is unit-safe, and every
  value-chain role plus confirmed edge direction has focused coverage.

## Out of scope

Live crawl SaaS, runtime LLM industry classification, stock trading.

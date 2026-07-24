# Evolution loop

## Operating mode (user)

- **Mode A (active):** short-interval **scheduler (~20m)** continues development + push without user typing.
- Session can still request intensive work while chat is open.
- Autonomous git: commit/push/tag on meaningful slices.
- Never push `.github/workflows/*` without `workflow` OAuth scope (use `docs/ci-github-actions.yml`).

## Shipped (through 0.1.37)

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

## Next

1. Real PatentsView dump (human data)
2. Enable Actions with workflow-scoped PAT (human)
3. Optional: `subject_raw` staging for unresolved mentions
4. Optional: self-audit note for Windows engine-only gate / Docker PARTIAL

## Out of scope

Live crawl SaaS, runtime LLM industry classification, stock trading.

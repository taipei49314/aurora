# Evolution loop (plan → execute → test → confirm → plan)

Living checklist for real-world AURORA evolution. Each loop is intentionally small.

## Operating mode

- Autonomous local development: commit/push/tag when a slice is ready
- Do **not** push under `.github/workflows/` (OAuth lacks workflow scope) — CI templates live in `docs/`
- Stay on AURORA: local-first, deterministic, no LLM-at-runtime classification, no stock features

## Shipped versions

| Ver | Highlights |
|-----|------------|
| 0.1.1 | OSS packaging, import-schema, adapters base |
| 0.1.2 | external_ids ER, multisource, resolve CLI/API |
| 0.1.3 | doctor, entities `?q=`, CI template, issue templates |
| 0.1.4 | OpenAlex adapter, Data Explorer server entity filter |
| 0.1.5 | `/api/stats`, source tier filters, dashboard cards, openalex case, language policy |

## Loop 15 (done) — reliability_tier filter + stats + openalex case

**Shipped (engine 0.1.5):**

- `GET /api/stats` — tier mix, external_ids coverage, obs type histogram
- `GET /api/sources?reliability_tier=` (+ comma lists, `?q=`)
- `GET /api/observations?observation_type=` (+ `?q=`)
- Data Explorer sources tab: A–D chips, tier badges, detail pane, docs links
- Dashboard: corpus stat cards + DQ column
- `cases/openalex-sample` scorecard in `scripts/check_all.py`
- README language policy
- Tests: stats, tier filter, sources q, observations type filter

**Confirm:** filter returns only matching tiers; invalid tier → 422; UI chips refetch.

## Loop 16 (next)

1. Real PatentsView dump (human data — not auto-fetch)
2. Filings adapter (10-K / 重大訊息 → CAPEX, tier A)
3. Observation type chips in Data Explorer UI
4. Merge openalex + patents into one demo package
5. Enable Actions workflow with PAT that has `workflow` scope (human)

## Out of scope

Live crawl service, multi-tenant SaaS, stock outputs, runtime LLM industry classification.

# Evolution loop

## Operating mode (user)

- **Mode A (active):** short-interval **scheduler (~20m)** continues development + push without user typing.
- Session can still request intensive work while chat is open.
- Autonomous git: commit/push/tag on meaningful slices.
- Never push `.github/workflows/*` without `workflow` OAuth scope (use `docs/ci-github-actions.yml`).

## Shipped (through 0.1.14)

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

## Next

1. Full document + span (`documents[]` / `char_span`) — large schema
2. Real PatentsView dump (human data)
3. Enable Actions with workflow-scoped PAT (human)

## Out of scope

Live crawl SaaS, runtime LLM industry classification, stock trading.

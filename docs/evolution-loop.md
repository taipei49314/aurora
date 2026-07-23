# Evolution loop

## Operating mode (user)

- **Mode A (active):** short-interval **scheduler (~20m)** continues development + push without user typing.
- Session can still request intensive work while chat is open.
- Autonomous git: commit/push/tag on meaningful slices.
- Never push `.github/workflows/*` without `workflow` OAuth scope (use `docs/ci-github-actions.yml`).

## Shipped (through 0.1.8)

| Ver | Highlights |
|-----|------------|
| 0.1.1–0.1.4 | OSS, adapters base, ER external_ids, OpenAlex, resolve |
| 0.1.5 | stats API, tier filters, dashboard |
| 0.1.6 | obs-type chips, filings adapter |
| 0.1.7 | five-adapter multisource case |
| 0.1.8 | source_type filter, package linter, scheduler mode A |

## Next

1. Source-type chips in Data Explorer UI  
2. Wire `lint_package` into `check_all`  
3. Real PatentsView dump (human)  
4. Enable Actions with workflow-scoped PAT (human)

## Out of scope

Live crawl SaaS, runtime LLM industry classification, stock trading.

# Evolution loop

## Operating mode (user)

- **Session-only intensive**: work hard while the conversation is open; no 30m scheduler.
- **Autonomous git**: commit/push/tag when a slice is ready (no workflow files under `.github/workflows/`).

## Shipped (through 0.1.5)

| Ver | Highlights |
|-----|------------|
| 0.1.1 | OSS packaging, import-schema, adapters base |
| 0.1.2 | external_ids ER, multisource, resolve CLI/API |
| 0.1.3 | doctor, entities `?q=`, CI template, issue templates |
| 0.1.4 | OpenAlex adapter, Data Explorer server filter |
| 0.1.5 | `/api/stats`, source tier filters, dashboard cards, openalex case |

## Next (when session continues)

1. Merge openalex + patents into one demo package
2. Observation type chips in Data Explorer
3. Real dump drop-in (human data)
4. Enable Actions workflow with PAT that has `workflow` scope (human)

## Out of scope

Live crawl SaaS, runtime LLM industry classification, stock trading outputs.

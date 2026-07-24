# AURORA Import Schema

Canonical contract for packages accepted by `import_package()` (`backend/aurora/importing.py`).

This document freezes **what the engine accepts today**, **how fields are used**,
**conventions for real-world adapters**, and **known gaps** before a schema bump.

Related code: `backend/aurora/models.py`, `importing.py`, `dedup.py`.
Examples: `examples/`. Machine-readable schema: `examples/schemas/import-package.schema.json`.

---

## 1. Package shape

Top-level JSON object:

```json
{
  "entities": [ /* EntityRow */ ],
  "sources": [ /* SourceRow */ ],
  "observations": [ /* ObservationRow */ ]
}
```

| Key | Required | Notes |
|-----|----------|--------|
| `entities` | yes (may be `[]`) | Canonical actors; ids are derived, not caller-supplied |
| `sources` | yes (may be `[]`) | Documents / records; linked from observations via `ref` |
| `observations` | yes (may be `[]`) | Atomic evidence rows |

There is **no** first-class `documents`, `mentions`, or `events` layer in v0.
Adapters must extract observations *before* import.

Import is **idempotent**: re-importing the same content yields the same
content-addressed ids and does not double-count evidence.

---

## 2. Date and time conventions (freeze these)

| Field | Meaning | Rule |
|-------|---------|------|
| `Source.published_at` | When the **document** was published or became public | ISO date `YYYY-MM-DD` preferred; full ISO datetime accepted (first 10 chars used) |
| `Observation.observed_at` | When the **underlying event** occurred | Prefer event date over crawl date; use `null` if unknown — **do not** invent with retrieve time |
| `Source.retrieved_at` | Set by importer to import wall-clock | Callers cannot override today |

**Leakage rule:** cutoff runs keep only observations with `observed_at <= cutoff`
(and treat missing dates per `leakage.py` / pipeline data-quality penalty).

Invalid date strings are recorded as import row errors (`SOURCE_DATE_MISSING`)
but do not always hard-fail the whole package.

---

## 3. Entity row

### Required

| Field | Type | Description |
|-------|------|-------------|
| `entity_type` | string enum | See §6 |
| `canonical_name` | non-empty string | Display + identity; normalized for ids |

### Optional

| Field | Type | Default | Engine use |
|-------|------|---------|------------|
| `aliases` | string[] | `[]` | Entity resolution / renames |
| `description` | string | `""` | Stored; light influence on features only if text is reused elsewhere |
| `country` | string | `""` | **Stored only** (not used in scoring/clustering today) |
| `external_ids` | `{system,id}[]` | `[]` | **First-class**; joins dumps; also under `metadata.external_ids` |
| `metadata` | object | `{}` | Opaque passthrough (`external_ids` lifted out if nested) |

### Derived (engine)

- `entity_id` = content-addressed from `(entity_type, normalize(canonical_name))` for the **first** row of that name
- Rows that share an `external_ids` key **merge** into the first owner (aliases ∪ external_ids)
- `created_at` = import timestamp

### Real-data conventions

```json
"external_ids": [
  {"system": "lei", "id": "5493001KJTIIGC8Y1R12"},
  {"system": "cik", "id": "0000320193"},
  {"system": "domain", "id": "example.com"},
  {"system": "uspto_assignee", "id": "123456"}
]
```

**Do not** invent industry labels in `metadata` that the engine should treat as ground truth.

### Observation subject / object resolution (engine 0.1.2+)

`subject` / `object` may be:

| Form | Example |
|------|---------|
| Name string | `"FerroGrid Power"` |
| Compact external ref | `"ext:lei:LEI-FERRO"` or `"lei:LEI-FERRO"` |
| Structured | `{"name": "Trade Name", "external_ids": [{"system":"lei","id":"…"}]}` |

Optional fields on the observation row:

- `subject_external_ids` / `object_external_ids` — disambiguate when the name is shared by two entities

Resolution order: unique external id → compact ext ref → name/alias → external disambiguation of ambiguous names.

---

## 4. Source row

### Required

| Field | Type | Description |
|-------|------|-------------|
| `source_type` | string enum | See §6 |
| `publisher` | non-empty string | Outlet, assignee office, journal, board, etc. |
| `title` | non-empty string | Document title |

### Strongly recommended

| Field | Type | Description |
|-------|------|-------------|
| `ref` | string | Caller key; **observations must set `source_ref` to this value** |

Without `ref`, observations cannot attach to the source.

### Optional

| Field | Type | Default | Engine use |
|-------|------|---------|------------|
| `published_at` | string \| null | null | Publication / grant date (audit + source leakage filter) |
| `event_date` | string \| null | null | **First-class** (engine 0.1.10+); activity / application / filing date. Metadata fallback accepted. Empty `observed_at` on observations falls back to `event_date` then `published_at` |
| `excerpt` | string | `""` | **Part of content hash** + near-duplicate tokens (also stored in `metadata.excerpt`) |
| `independence_group` | string | auto or `""` | Declared non-independence; if empty, engine derives from `metadata.wire_id` → `wire:…`, `outlet_domain` → `domain:…`, or `family_id` → `family:…` (0.1.1+) |
| `family_id` | string | `""` | **First-class** (engine 0.1.8+); patent/document family. Metadata fallback still accepted; promoted onto `Source.family_id`. When `independence_group` empty → `family:<id>` |
| `event_id` | string | `""` | **First-class** (engine 0.1.11+); real-world event key. Sources sharing `event_id` are not independent (dedup layer 2b). When `independence_group` empty → `event:<id>` (after wire/domain/family) |
| `outlet_domain` | string | `""` | **First-class** (engine 0.1.12+); digital outlet host. Metadata fallback. When `independence_group` empty → `domain:<host>` (after wire) |
| `wire_id` | string | `""` | **First-class** (engine 0.1.12+); news wire / syndication key. Metadata fallback. When `independence_group` empty → `wire:<id>` (highest priority auto-derive) |
| `geo` | object | `{}` | **First-class** (engine 0.1.13+); keys: `country`, `region`, `city`, `raw`, `jurisdiction`. Accepts `location` alias and top-level `country` / `jurisdiction` shorthands. Metadata fallback. |
| `license` | string | `""` | **First-class** (engine 0.1.14+); redistribution terms (SPDX-ish: `cc-by-4.0`, `public-patent-text`, …). Metadata fallback; package-level `license` / `package.license` / `meta.license` fills gaps |
| `reliability_tier` | `"A"\|"B"\|"C"\|"D"` | `"C"` | **Scored** via data_quality_penalty (engine 0.1.1+); stamped onto observation metadata at import |
| `url_or_local_path` | string | `""` | Provenance |
| `language` | string | `"en"` | **Stored only** today |
| `metadata` | object | `{}` | Opaque passthrough |

### Derived (engine)

- `content_hash` = hash(`source_type`, normalized `title`, normalized `excerpt`, `publisher`)
- `source_id` = content-addressed from that hash
- `retrieved_at` = import time

**Warning:** changing excerpt truncation length changes `content_hash` and thus `source_id`.
Adapters should canonicalize excerpt (e.g. first 500 chars of abstract, stable whitespace).

### Real-data conventions (metadata + independence)

```json
"independence_group": "wire:reuters",
"license": "cc-by-4.0",
"metadata": {
  "external_ids": [{"system": "doi", "id": "10.1234/foo"}],
  "extractor_id": "patent-adapter",
  "extractor_version": "0.1.0"
}
```

### Public-corpus license policy (engine 0.1.14+)

Redistribution of real dumps requires an explicit license per source (or a package
default). The engine does **not** block import without licenses (research corpora
may be private), but the linter can enforce the policy:

```bash
PYTHONPATH=backend python scripts/lint_package.py path/to/package.json --public-corpus
# or: --require-license

# Fail when observation.document_id has no documents[] row (0.1.22+)
PYTHONPATH=backend python scripts/lint_package.py path/to/package.json --require-documents

# Span policy (0.1.26+): every document_id obs must have char_span after import,
# and/or overall span ratio must meet a floor
PYTHONPATH=backend python scripts/lint_package.py path/to/package.json --require-char-spans
PYTHONPATH=backend python scripts/lint_package.py path/to/package.json --min-char-span-ratio 0.5
```

Suggested license strings (not an exhaustive legal list):

| String | Typical use |
|--------|-------------|
| `public-patent-text` | Published patent full text (verify jurisdiction) |
| `cc-by-4.0` / `cc0-1.0` | Creative Commons open text |
| `company-release` | Official press/IR release |
| `proprietary` / `all-rights-reserved` | Not redistributable publicly |
| `unknown` | Honesty when the dump does not declare terms |

Suggested `independence_group` prefixes (adapters should set these, not leave empty when known):

| Prefix | Meaning |
|--------|---------|
| `wire:<name>` | Same news wire / syndication family |
| `domain:<host>` | Same digital outlet |
| `family:<patent_family_id>` | Same patent family |
| `event:<event_id>` | Same real-world event (engine 0.1.11+) |
| `reprint:<hash>` | Known republication of identical body |

---

## 5. Observation row

### Required

| Field | Type | Description |
|-------|------|-------------|
| `source_ref` | string | Must match a source `ref` (or, after export, a `source_id`) |
| `observation_type` | string enum | See §6; **semantic label, not raw API field** |
| `subject` **or** `subject_raw` | string / object | At least one required (0.1.38+). `subject` is the resolvable ref (name, ext, or structured); `subject_raw` alone is used as the mention string for resolution when `subject` is omitted |

### Optional

| Field | Type | Default | Engine use |
|-------|------|---------|------------|
| `object` | string \| null | null | Other entity name for relational edges |
| `subject_raw` | string | derived | **First-class** (engine 0.1.38+); surface-form mention as written in the source (alias, trade print, compact ext ref). Explicit top-level / metadata wins; otherwise derived from `subject`. Stored on `Observation.subject_raw`; export round-trips it. Does **not** invent entities — unresolved names still error |
| `object_raw` | string | derived | **First-class** (engine 0.1.38+); same staging rules for the object mention |
| `observed_at` | string \| null | null | Temporal signals, leakage, fade |
| `event_id` | string | `""` | **First-class** (engine 0.1.11+); real-world event. Metadata fallback; inherits `Source.event_id` when empty |
| `geo` | object | `{}` | **First-class** (engine 0.1.13+); location/jurisdiction. Inherits `Source.geo` when empty. Accepts `location` / `country` / `jurisdiction` aliases |
| `document_id` | string | `""` | **First-class** (engine 0.1.15+); links to optional `documents[]` row or source-as-document id. Metadata fallback |
| `char_span` | `[start, end]` \| null | null | **First-class** (engine 0.1.15+); character offsets into document text. Also accepts `{start, end}` |
| `text_excerpt` | string | `""` | **Primary feature text** (TF-IDF / naming) |
| `confidence` | number 0..1 | `0.7` | Edge weights for relational types |
| `numeric_value` | number \| null | null | Lead-time / capacity heuristics |
| `unit` | string \| null | null | Free string today; see §8 |
| `metadata` | object | `{}` | Import merges `source_type` + resolved independence |

### Optional `documents[]` (engine 0.1.15+)

Full-text / path records. Observations point here via `document_id` (+ optional `char_span`).

| Field | Type | Description |
|-------|------|-------------|
| `document_id` | string | Required stable id |
| `source_ref` | string | Optional link to a source `ref` |
| `title` | string | Document title |
| `text` / `body` | string | Optional full text (may be empty if only a path) |
| `url_or_local_path` | string | File or URL provenance |
| `language` | string | Default `en` |
| `license` | string | Redistribution terms for this document |
| `metadata` | object | Opaque |

Not required for scoring; enables span-level provenance for real dumps.

**Adapter auto-build (0.1.19+):** offline adapters call
`adapters.package_util.ensure_documents` so each `observation.document_id`
that equals a `source.ref` gets a `documents[]` row with `text` from the
source `excerpt` (title/url/license copied). Existing rows with text are
never overwritten. `metadata.auto_built=true` marks generated rows.
`strip_package` and `merge_packages` preserve / merge `documents[]`.

**char_span auto-align (0.1.20+ / progressive 0.1.24+):** when an observation
has `document_id` and `text_excerpt` but no `char_span`, the engine (and
`ensure_documents`) locate the excerpt inside document text — exact →
case-insensitive → whitespace-flexible → **progressive word/char prefix** —
and set `[start, end]` with `metadata.char_span_auto`. Explicit spans are
never overwritten. Snapshot count: `char_spans_auto_aligned`.

Curated demos may call `align_observation_char_spans(pkg, append_unmatched=True)`
to append still-unmatched excerpts onto the document body
(`metadata.char_span_appended`).

**lint document policy (0.1.22+):** `lint_package` always reports
`orphan_document_ids` (observation `document_id` with no `documents[]` row).
`--require-documents` fails the package when any orphan exists. Prefer
adapter `ensure_documents` or an explicit `documents[]` array.

### Resolution rules

- `subject` / `object` are resolved by **normalized name / alias** (and external ids; see §3).
- Unknown name → row error, observation dropped; error `value` carries `subject_raw` when known (0.1.38+).
- `subject_raw` / `object_raw` are **provenance only** after a successful resolve — they do not change content-addressed observation ids.
- Ambiguous name (maps to >1 entity) → error, not a silent pick.

### Real-data conventions (metadata)

```json
"document_id": "doc_us2024123456a1",
"char_span": [120, 480],
"metadata": {
  "classification_codes": ["H01M-10/054", "H01M-4/58"],
  "currency": "USD",
  "amount_original": 120000000,
  "geo": {"country": "US", "region": "AZ"},
  "valid_from": "2024-01-15",
  "valid_to": "2024-06-30"
}
```

---

## 6. Controlled vocabularies

### `source_type`

`COMPANY_FILING` · `PATENT` · `PAPER` · `JOB_POSTING` ·
`NEWS` · `GOVERNMENT_PROGRAM` · `STANDARD` · `RESEARCH_NOTE`

### `entity_type`

`COMPANY` · `RESEARCH_INSTITUTE` · `UNIVERSITY` · `GOVERNMENT` · `STANDARD_BODY` ·
`PRODUCT` · `TECHNOLOGY` · `MATERIAL` · `COMPONENT` · `PROCESS` · `FACILITY` ·
`APPLICATION` · `MARKET` · **`PERSON`** (engine 0.1.16+)

`PERSON` is for inventors, authors, and founders. They are **not** industry-clusterable
(`CLUSTERABLE_TYPES` excludes them) so they do not form industry hypotheses alone.
USPTO / PatentsView adapters emit `PERSON` from inventor lists; OpenAlex emits
`PERSON` from authorships (engine 0.1.17+) with optional `orcid` / `openalex_author` ids.

### `observation_type`

| Group | Types | Role in engine |
|-------|-------|----------------|
| Real investment | `PATENT_ACTIVITY`, `HIRING_ACTIVITY`, `CAPEX_ACTIVITY`, `CAPACITY_EXPANSION`, `SUPPLIER_RELATIONSHIP`, `STANDARD_ACTIVITY` | Counter-hype, candidate gates |
| Demand | `CUSTOMER_RELATIONSHIP`, `ADOPTION_SIGNAL`, `DEMAND_SIGNAL` | Demand score |
| Narrative | `PRODUCT_LAUNCH`, `STRATEGIC_INVESTMENT` (+ NEWS sources) | Hype if dominant |
| Negative | `CANCELLATION_SIGNAL`, `SHUTDOWN_SIGNAL`, `PRICE_PRESSURE`, `LEAD_TIME_PRESSURE` | Counterevidence / constraints |
| Structural | `TECHNICAL_DEPENDENCY`, `RESEARCH_ACTIVITY`, `REGULATORY_SUPPORT` | Graph / chain / regulation |

Relational types that **should** set `object` when known:

`SUPPLIER_RELATIONSHIP` · `CUSTOMER_RELATIONSHIP` · `TECHNICAL_DEPENDENCY` · `STRATEGIC_INVESTMENT`

### `reliability_tier` (stored)

| Tier | Intent |
|------|--------|
| A | Official filings, primary legal/patent registers |
| B | Reproducible technical docs, peer-reviewed |
| C | News / secondary reporting |
| D | Social, unverified blogs, pure syndication sinks |

---

## 7. Independence and dedup (what adapters must get right)

Pipeline (`dedup.py`):

1. **Exact** — same `content_hash`
2. **Declared** — same non-empty `independence_group`
3. **Near-dup** — high token overlap on `title` + `excerpt` (MinHash-LSH)

Scoring uses **independent source counts**, not raw row counts.
If adapters leave `independence_group` empty for wire reprints, independence is **overstated**.

---

## 8. Units and numbers (v0 freeform)

Preferred `unit` strings when `numeric_value` is set:

| Context | unit | numeric_value meaning |
|---------|------|------------------------|
| Open roles | `openings` | headcount openings |
| Capex | `USD` / `TWD` / `EUR` | amount in that currency (**no FX normalization in engine**) |
| Lead time | `months` | months (bottleneck scales `/24`) |
| Capacity delta | `pct` or physical unit | negative used as capacity stress signal |

Document currency also under `metadata.currency` when unit is ambiguous.

---

## 9. Real-source mapping cheat sheet

| Real source | `source_type` | Typical `observation_type` | Must carry |
|-------------|---------------|----------------------------|------------|
| Patent office | `PATENT` | `PATENT_ACTIVITY` | abstract→excerpt; assignee→entity; codes→metadata |
| Job board | `JOB_POSTING` | `HIRING_ACTIVITY` | skills in `text_excerpt`; openings numeric |
| 10-K / 重大訊息 | `COMPANY_FILING` | `CAPEX_ACTIVITY`, `CAPACITY_EXPANSION` | tier `A`; amount+currency |
| News / wire | `NEWS` | often mirrors event type, or narrative-only | **wire independence_group** |
| Standard body | `STANDARD` | `STANDARD_ACTIVITY` | standard id in metadata |
| Paper | `PAPER` | `RESEARCH_ACTIVITY` | DOI in external_ids |
| Supply contract note | filing/news | `SUPPLIER_RELATIONSHIP` | **object** required for graph credit |

See also:

- `examples/real_mini_package.json` — hand-authored multi-source package
- `adapters/` — offline converters (`uspto`, `patentsview`, `jobs`, `news`, `merge`)
- `adapters/fixtures/uspto_sample.json` — simple USPTO-shaped input
- `adapters/fixtures/patentsview_sample.json` — PatentsView field names (swap for real export)
- `cases/patentsview-sample/` — end-to-end dump → package → scorecard

---

## 10. What is intentionally missing (v0 gaps)

Do **not** assume these exist as first-class fields:

| Gap | Workaround today | Candidate future field |
|-----|------------------|------------------------|
| External IDs | **done** first-class `external_ids[]` (+ metadata fallback) | use in ER join rules |
| Full document + span | **done** `documents[]` + first-class `document_id` / `char_span` | text may still be empty (path-only) |
| Unresolved mentions | **done** first-class `subject_raw` / `object_raw` (surface form + subject_raw-only resolve); still must resolve to an entity | optional future: provisional entities |
| Patent family | **done** first-class `family_id` (+ metadata fallback) | use in independence / export |
| Dual dates (app vs grant) | **done** first-class `event_date` + `published_at` | observe_at fallback uses event_date |
| Outlet auto-independence | **done** first-class `outlet_domain` + `wire_id` | derive independence_group |
| Event-level dedup | **done** first-class `event_id` on Source + Observation | independence layer 2b |
| Geo / jurisdiction in model | **done** first-class `geo` on Source + Observation | entity.country already first-class |
| reliability in score | **done (engine 0.1.1)** via data_quality_penalty | optional: tier-weighted independence |
| License for redistribution | **done** first-class `Source.license` + package default | `lint_package --public-corpus` |
| PERSON entities | **done** optional `PERSON` type (not clusterable) | inventors via patent adapters |

Engine evolution should prefer **small schema increments** listed in the project
schema gap analysis over adding many unused columns.

---

## 11. Validation and CLI

```bash
# structural + engine import (recommended)
PYTHONPATH=backend python scripts/validate_package.py examples/real_mini_package.json

# optional: also run a discovery pass (needs taxonomy)
PYTHONPATH=backend python scripts/validate_package.py examples/real_mini_package.json --run

# JSON Schema only (if jsonschema installed)
PYTHONPATH=backend python scripts/validate_package.py examples/real_mini_package.json --schema-only
```

Makefile: `make validate-example`

---

## 12. Export round-trip

`GET /api/exports` emits the same three arrays with:

- source `ref` = internal `source_id`
- observation `subject`/`object` as **canonical names**
- `excerpt` lifted out of source metadata so content hashes recompute identically

Feed the export back into `POST /api/imports` for a round-trip check.

---

## 13. Versioning

| Item | Value |
|------|-------|
| Document | import-schema 0.1.0 |
| Engine package | see `config.ENGINE_VERSION` |
| Breaking changes | require engine minor bump + example updates |

When adding first-class fields, update:

1. `models.py` / `importing.py`
2. this document
3. `examples/schemas/import-package.schema.json`
4. at least one example package + `scripts/validate_package.py` expectations

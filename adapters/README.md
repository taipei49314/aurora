# AURORA adapters (offline)

Convert **caller-supplied** source dumps into import packages
(`{entities, sources, observations}`). See [`docs/import-schema.md`](../docs/import-schema.md).

## Rules

- No network I/O inside adapters
- No LLM at runtime
- Do not invent facts not present in the input JSON
- Prefer explicit ontology hooks / claims over keyword guessing

## Commands

```bash
python -m adapters uspto adapters/fixtures/uspto_sample.json -o /tmp/p.json --strip --validate
python -m adapters patentsview adapters/fixtures/patentsview_sample.json -o /tmp/pv.json --strip --validate
python -m adapters jobs  adapters/fixtures/jobs_sample.json  -o /tmp/j.json --strip --validate
python -m adapters news  adapters/fixtures/news_sample.json  -o /tmp/n.json --strip --validate

python -m adapters merge /tmp/p.json /tmp/j.json /tmp/n.json -o /tmp/combined.json --strip --validate --strict
```

Makefile:

```bash
make adapt-uspto
make adapt-merge-demo      # builds cases/iron-air-mini/package.json + scorecard check
make patentsview-sample    # PatentsView-compatible dump case
```

## Source mapping

| Adapter | Input key | source_type | Typical observations |
|---------|-----------|-------------|----------------------|
| `uspto` | `patents[]` (simple shape) | `PATENT` | `PATENT_ACTIVITY`, `TECHNICAL_DEPENDENCY` |
| `patentsview` | `patents[]` / `results[]` (PatentsView fields) | `PATENT` | same via normalize → uspto |
| `jobs` | `postings[]` | `JOB_POSTING` | `HIRING_ACTIVITY` (+ weak tech edges) |
| `news` | `articles[]` + `claims[]` | `NEWS` | whatever claims declare (`SUPPLIER_RELATIONSHIP`, …) |

### Independence conventions

| Adapter | `independence_group` |
|---------|----------------------|
| USPTO | `family:<family_id>` or `patent:<pub>` |
| Jobs | `domain:<host>` or `job:<id>` |
| News | `wire:<wire_id>` (reprints inherit primary wire); else `domain:` |

News reprints: set `is_reprint_of` to the primary article `id` **and** share `wire_id` when known.

## Fixtures

| File | Role |
|------|------|
| `fixtures/uspto_sample.json` | 3 patents (shared family) |
| `fixtures/patentsview_sample.json` | 4 patents, PatentsView field names (replaceable) |
| `fixtures/jobs_sample.json` | 3 postings (hiring) |
| `fixtures/news_sample.json` | wire + reprint + pilot article |

## Adding another source

1. Define offline JSON shape under `adapters/fixtures/`
2. Implement `convert_<source>(raw: dict) -> package`
3. Register subcommand in `adapters/__main__.py`
4. Export from `adapters/__init__.py`
5. Add `tests/test_adapters_<source>.py` (zero import row errors)

# AURORA

**Unknown Industry Discovery Engine** — local-first, deterministic, evidence-grounded.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Engine](https://img.shields.io/badge/engine-0.1.35-blue.svg)](CHANGELOG.md)

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](backend/requirements.txt)

AURORA looks for **industries that may be forming but are not yet named**, from
dispersed signals (patents, hiring, capex, supply chain, standards, news, notes).

It is **not** a stock tool: it never outputs BUY/SELL, target prices, or return forecasts.

> **Design principles:** local-first · single-user · reproducible · evidence-grounded ·
> time-aware · auditable · **no external API / LLM at runtime** · no fabricated evidence ·
> **no future-data leakage** · no forced industry conclusion.

## Why this is not “summarize articles with an LLM”

Every classification is a **deterministic, explainable function of the data**.
The engine clusters cross-source structure, compares to a known taxonomy, hunts
**counter**evidence, and can re-run at a historical cutoff with a hard leakage check.

| Status | Meaning |
|--------|---------|
| `INDUSTRY_CANDIDATE` | Structurally complete, demand-backed, not just narrative |
| `EXISTING_INDUSTRY_VARIANT` | Looks like a rebrand of a known industry |
| `HYPE_CLUSTER` | Loud but hollow |
| `INSUFFICIENT_EVIDENCE` | Not enough independent signal |
| `REJECTED` / `DORMANT` | Counterevidence dominates |

## Quick start

**Requirements:** Python **3.9+** (3.11+ recommended). Core engine is **stdlib-only**.

```bash
git clone https://github.com/taipei49314/aurora.git
cd aurora

# optional: API + tests (needs SQLAlchemy; on Windows may require MSVC for greenlet)
python -m pip install -r backend/requirements.txt

# Windows without C++ Build Tools — engine tests only (recommended default):
python -m pip install -r backend/requirements-engine-test.txt

# Windows PowerShell
$env:PYTHONPATH = "backend"
# Unix
# export PYTHONPATH=backend

python backend/aurora/cli.py          # demo: generate corpus → classify
python scripts/check_engine.py        # engine gate (skips API/SQL tests)
python -m pytest tests/ -q            # full suite (needs full requirements)
python scripts/check_all.py --engine-only   # same as check_engine
python scripts/check_all.py           # full pre-push: tests + cases + resolve smoke
```

With Make (if available):

```bash
make demo
make test
make check-all    # recommended before release push
make backtest
make api          # FastAPI :8000
make frontend     # Vite :5173
```

### Demo output (Northstar synthetic corpus)

```
STATUS                       OVERALL  HYPE CONTRA   SIM  NAME
INDUSTRY_CANDIDATE              73.8     7      5  0.00  analog-inference-compute-in-memory ...
HYPE_CLUSTER                    27.9    89      0  0.00  quantum-mining-superposition-hash
INSUFFICIENT_EVIDENCE           25.0    73     55  0.00  volumetric-display-free-space-optics
```

## Bring your own data (import package)

Guide for real offline dumps: [docs/real-dump-guide.md](docs/real-dump-guide.md).

AURORA does **not** crawl the web. Feed a JSON package:

```json
{ "entities": [], "sources": [], "observations": [] }
```

| Resource | Purpose |
|----------|---------|
| [docs/import-schema.md](docs/import-schema.md) | Field contract, dates, independence, real-source mapping |
| [examples/real_mini_package.json](examples/real_mini_package.json) | Multi-source hand-authored sample |
| [examples/schemas/import-package.schema.json](examples/schemas/import-package.schema.json) | JSON Schema |
| [adapters/](adapters/) | Offline converters (USPTO-shaped, PatentsView-compatible, jobs, news, merge) |
| [cases/](cases/) | Scorecarded demos (merge, retro cutoffs, PatentsView sample) |

```bash
# validate a package
PYTHONPATH=backend python scripts/validate_package.py examples/real_mini_package.json --run

# offline PatentsView-shaped dump → package
python -m adapters patentsview cases/patentsview-sample/dump.json --validate --strict

# temporal honesty gates (curated timeline — not real-world lead-time proof)
PYTHONPATH=backend python scripts/run_retro_case.py cases/iron-air-retro
```

## Architecture

```
Snapshot → Features → Clustering → Taxonomy → Naming gap
        → Value chain → Bottleneck → Hype + counterevidence
        → Transparent scoring → Classification → Research run
```

Docs: [architecture](docs/architecture.md) · [scoring](docs/scoring-model.md) ·
[hype filter](docs/hype-filter.md) · [leakage](docs/leakage-prevention.md) ·
[import schema](docs/import-schema.md) · [self-audit](docs/self-audit.md) ·
[evolution loop](docs/evolution-loop.md)

## Honesty (read before starring)

- **Not investment advice.** No trading outputs.
- **Northstar demo metrics** are on a **synthetic** corpus with ground truth.
- **Retro case** (`cases/iron-air-retro`) tests **engine time behavior** on curated data —
  it does **not** claim real-world early discovery of iron-air storage.
- **PatentsView sample dump** is a **format-compatible fixture** by default; replace
  `dump.json` with a real export without code changes.
- See [docs/self-audit.md](docs/self-audit.md) for PASS / PARTIAL items (e.g. Docker not verified on all machines).

## Layout

```
backend/aurora/   discovery engine (pure stdlib) + CLI
backend/api.py    FastAPI layer
adapters/         offline source converters
cases/            release demos + scorecards
datasets/         Northstar generator + taxonomy
docs/             architecture, models, import-schema, release notes
examples/         import packages + JSON Schema
frontend/         Vite + React + TS (8 pages)
scripts/          validate / retro / scorecard helpers
tests/            pytest (unit / integration / e2e)
```

## Version

- Engine: **0.1.35** — see [CHANGELOG.md](CHANGELOG.md)
- License: **MIT** — see [LICENSE](LICENSE)
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)
- Security: [SECURITY.md](SECURITY.md)
- Release checklist: [docs/RELEASE.md](docs/RELEASE.md)

## Language policy (UI / cases)

| Layer | Language |
|-------|----------|
| Engine, API field names, statuses, logs | **English-first** (stable machine contract) |
| Frontend chrome (nav, labels) | English |
| Case honesty notes / scorecards | English primary; **bilingual Chinese optional** for human narrative |
| Imported source text / excerpts | Preserve source language as-is |

Do not localize enum values (`INDUSTRY_CANDIDATE`, observation types, etc.) —
adapters and tests depend on the English controlled vocabulary.

## Citation

If AURORA helps your research, please cite the repository URL and version tag
(e.g. `v0.1.1`). A formal paper is not required for use.

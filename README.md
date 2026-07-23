# AURORA — Unknown Industry Discovery Engine

Local-first research system that finds **industries that may be forming but are
not yet named or widely understood**, from dispersed signals (patents, hiring,
capex, supply chain, standards, news, research notes). It is **not** a stock
tool: it never outputs BUY/SELL, target prices, or return forecasts.

> Design principles (spec §2): local-first · single-user · reproducible ·
> evidence-grounded · time-aware · auditable · **no external API/LLM at runtime**
> · no fabricated evidence · **no future-data leakage** · no forced industry
> conclusion.

## Why this is not "summarize articles with an LLM"
Every classification is a **deterministic, explainable function of the data**.
The engine forms clusters from cross-source structure, compares them to a known
industry taxonomy, actively hunts **counter**evidence, and can be re-run at a
historical cutoff with a hard guarantee of no future-data leakage. If evidence
is thin it says `INSUFFICIENT_EVIDENCE`; if a cluster is loud but hollow it says
`HYPE_CLUSTER`; if it's a rebrand it says `EXISTING_INDUSTRY_VARIANT`. Only
genuine, structurally-complete, demand-backed clusters reach `INDUSTRY_CANDIDATE`.

## Quick start (no third-party runtime deps for the core)
```bash
# core engine + demo (pure standard-library Python 3.11+)
make demo          # generate corpus -> run discovery -> print classified hypotheses

# tests (needs pytest + hypothesis)
make install
make test          # 78 tests (51 unit / 14 integration / 13 e2e)

# historical backtest (early-discovery lead time, leakage check)
make backtest

# measured per-stage performance
make benchmark

# API + minimal UI
make api            # FastAPI on :8000
make frontend       # Vite dev server on :5173 (needs npm install)
```

## What one `make demo` shows
```
STATUS                       OVERALL  HYPE CONTRA   SIM  NAME
INDUSTRY_CANDIDATE              73.8     7      5  0.00  analog-inference-compute-in-memory ...   (neuromorphic edge sensing)
INDUSTRY_CANDIDATE              73.5     7      5  0.01  dispatchable-firming-depth-discharge ... (iron-air long-duration storage)
INDUSTRY_CANDIDATE              72.5     7      6  0.00  biofabricated-structural-panel ...       (mycelium materials)
EXISTING_INDUSTRY_VARIANT       57.6    19      0  0.57  assembly-drivetrain-casting              (rebranded auto components)
EXISTING_INDUSTRY_VARIANT       56.4    19      0  0.61  fabric-redundancy-bandwidth              (rebranded data centers)
HYPE_CLUSTER                    27.9    89      0  0.00  quantum-mining-superposition-hash        ("quantum" does NOT inflate)
HYPE_CLUSTER                    27.6    88      0  0.00  avatar-shopping-nft-checkout             (metaverse retail)
INSUFFICIENT_EVIDENCE           25.0    73     55  0.00  volumetric-display-free-space-optics     (single-giant pseudo-cluster)
REJECTED                        21.7    47    100  0.00  photobioreactor-triacylglycerol          (failed algae jet fuel)
```

## Architecture
`docs/architecture.md` (data model, pipeline stages, determinism), plus model
docs: `scoring-model`, `hype-filter`, `clustering-model`, `leakage-prevention`,
and ADRs in `docs/adr/`.

```
Research Snapshot -> Feature Construction -> Similarity Graph + Feature Clustering
-> Stability -> Taxonomy Comparison -> Naming Gap -> Value Chain -> Bottleneck
-> Evidence + Counterevidence -> Transparent Scoring -> Classification -> Research Run
```

## Honesty
See **`docs/self-audit.md`** for a per-requirement PASS/PARTIAL/NOT_IMPLEMENTED
scorecard. This is a single-session vertical slice: the discovery engine, data
foundation, historical validation, API and a minimal UI are done and verified;
Docker-verified deploy, Alembic migrations, and API import-upload/export are
tracked as PARTIAL.

## Layout
```
backend/aurora/   discovery engine (pure stdlib) + CLI
backend/api.py    FastAPI layer
datasets/         Northstar corpus generator + industry taxonomy
frontend/         Vite + React + TS (8 pages: Dashboard, Hypothesis Explorer,
                  Discovery Map, Timeline, Bottleneck Lab, Backtest Lab, Data Explorer, Run Comparison)
tests/            pytest suite (unit / integration / e2e / property / quality)
docs/             architecture, model docs, ADRs, self-audit
benchmarks/ scripts/
```

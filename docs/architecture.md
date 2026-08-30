# Architecture

## Overview
AURORA is a pipeline of small, independently-tested modules. There is **no
monolithic `discover_industries()`** (spec §10 forbids it). Data flows one
direction; every stage is a pure function of its inputs plus the versioned
config, which is what makes runs reproducible.

```
raw package
  └─ importing.py         schema-validate → canonicalize → resolve entities
                          → dedup/independence → temporal-validate → Snapshot (read-only contract)
Snapshot
  └─ leakage.py           apply cutoff, assert no future data
  └─ features.py          entity documents → TF-IDF + n-grams + obs-type dims
  └─ clustering.py        feature-space single-linkage  ┐
     graph.py             label-propagation communities  ┘ two comparable methods
  └─ clustering.py        bootstrap stability
  └─ taxonomy.py          similarity to known industries
  └─ naming_gap.py        capability coherence vs name dispersion
  └─ signals.py           per-entity strength / acceleration / independence
  └─ hype.py              narrative-vs-substance risk
  └─ counterevidence.py   supporting/counter/missing evidence, disconfirmation
  └─ value_chain.py       roles + evidence-linked edges
  └─ bottleneck.py        Brandes betweenness + derived substitutability
  └─ scoring.py           transparent weighted overall score
  └─ classify.py          status gates (§3)
  └─ pipeline.py          assembles the read-only-contract ResearchRun
```

## Data model (`models.py`, spec §6)
Plain dataclasses: `Source, Entity, Observation, Signal, Hypothesis,
EvidenceLink, ValueChainNode, BottleneckCandidate`. Controlled vocabularies are
string constants for stable, diffable snapshots.

## Determinism (spec §22, §29)
- **Generated content IDs** (`ids.py`) hash stable normalized fields. Imported
  external/document ids remain caller-visible stable keys. Re-importing the
  same package produces the same row ids, so dedup does not double-count it.
- **Two snapshot identities**: `snapshot_id` preserves the sorted row-id-set
  contract; the versioned `input_manifest_hash` covers full normalized payloads.
  `run_id` includes both, so same row ids with changed content cannot collide.
- **Stable ordering** everywhere: sorted iteration, tie-breaks on smallest id,
  fixed RNG seed for the stability bootstrap.
- **Config, not code**, drives every threshold/weight (`config.py`). Changing a
  weight forces a new `run_id` (hashes include the config manifest).
- Verified: `test_determinism_50_runs` — 50 runs, identical result-manifest hash.

## Reproducibility / provenance
A `ResearchRun` records `snapshot_id`, `cutoff_date`, engine/feature/taxonomy
versions, algorithm + scoring config, and input/result manifest hashes. Every
hypothesis carries its `observation_ids` and a full `score_explanation`.

## Why pure standard library
See `adr/0001-pure-python-core.md`. Summary: determinism (no BLAS thread
non-determinism), offline/local-first, and zero-friction install on restricted
networks. scikit-learn / networkx are optional accelerators, not runtime deps.

## Model docs

- [Feature model](feature-model.md)
- [Clustering model](clustering-model.md)
- [Scoring model](scoring-model.md)
- [Hype filter](hype-filter.md)
- [Value-chain model](value-chain-model.md)
- [Counterevidence model](counterevidence-model.md)
- [Bottleneck model](bottleneck-model.md)
- [Leakage prevention](leakage-prevention.md)
- [Backtest methodology](backtest-methodology.md)
- [Threat model](threat-model.md)

## Frontend / API
`backend/api.py` (FastAPI) exposes runs, hypotheses, evidence, value chain,
bottlenecks, backtests and run divergence. `frontend/` is a Vite+React+TS SPA;
the Dashboard + Hypothesis Explorer are implemented against that contract.

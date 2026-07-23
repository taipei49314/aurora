# ADR 0001 — Pure standard-library discovery core

## Status
Accepted.

## Context
The spec names scikit-learn, NetworkX, NumPy, etc. as the stack, but also
demands: local-first, offline, **no external API/LLM at runtime**, and
**bit-stable determinism over 50 runs** (§29). The build/target machines have
constrained package installation (TLS interception, no guaranteed pip), and
BLAS-backed libraries can introduce thread-order non-determinism.

## Decision
Implement the discovery engine (features, clustering, graph community detection,
scoring, bottleneck betweenness, etc.) in **pure Python standard library**.
Treat scikit-learn / NetworkX / SciPy / Polars as **optional accelerators**,
declared but commented in `requirements.txt`.

## Consequences
- **+** Runs anywhere with a Python 3.11+ interpreter, zero install, fully
  offline. `make demo` works out of the box.
- **+** Determinism is trivial to guarantee (sorted iteration, fixed seeds, no
  hidden parallelism). Proven by `test_determinism_50_runs`.
- **+** The algorithms are readable and auditable end-to-end — no black-box.
- **−** O(n²) similarity/near-dup passes; fine at MVP scale (~300 ms), needs
  LSH/blocking for the full corpus. Tracked in `clustering-model.md`.
- **−** We re-implement TF-IDF, cosine, label propagation and Brandes
  betweenness. These are small, well-tested, and covered by property tests.

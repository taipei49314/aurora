"""Source deduplication and independence (spec §8).

Source count must never equal evidence count. A press release reprinted by 20
outlets is at most one independent source. We resolve independence in three
layers, from strongest to weakest signal:

1. Exact duplicate  -> identical content_hash.
2. Declared group   -> sources sharing an explicit ``independence_group`` (e.g.
   same corporate parent, same wire service) are treated as one.
3. Near-duplicate   -> high token-Jaccard on title+excerpt (syndicated reprints
   that don't declare a group) get merged via union-find.

The output assigns every source a ``resolved_independence_group`` and reports
raw / deduplicated / independent counts.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict

from .features import tokenize

NEAR_DUP_JACCARD = 0.82

# MinHash-LSH parameters. 48 hashes split into 12 bands of 4 rows. The LSH
# candidate threshold ~ (1/bands)^(1/rows) ≈ 0.54, comfortably below the final
# NEAR_DUP_JACCARD gate, so all true near-duplicates become candidates while the
# number of exact jaccard comparisons stays near-linear instead of O(n^2).
_MINHASH_N = 48
_LSH_BANDS = 12
_LSH_ROWS = 4


def _hash_shingle(shingle: str, seed: int) -> int:
    h = hashlib.blake2b(shingle.encode("utf-8"), digest_size=8, salt=seed.to_bytes(2, "big"))
    return int.from_bytes(h.digest(), "big")


def _minhash_signature(shingles: set[str]) -> tuple[int, ...] | None:
    if not shingles:
        return None
    sig = []
    for seed in range(_MINHASH_N):
        sig.append(min(_hash_shingle(s, seed) for s in shingles))
    return tuple(sig)


def _lsh_candidate_pairs(signatures: dict[str, tuple[int, ...]]) -> set[tuple[str, str]]:
    """Bucket sources by signature bands; any two in the same band bucket are a
    candidate near-duplicate pair. Deterministic (sorted iteration)."""
    buckets: dict[tuple[int, int], list[str]] = defaultdict(list)
    for sid in sorted(signatures):
        sig = signatures[sid]
        for band in range(_LSH_BANDS):
            rows = sig[band * _LSH_ROWS:(band + 1) * _LSH_ROWS]
            key = (band, hash(rows))
            buckets[key].append(sid)
    pairs: set[tuple[str, str]] = set()
    for members in buckets.values():
        if len(members) < 2:
            continue
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                pairs.add(tuple(sorted((members[i], members[j]))))
    return pairs


class _UnionFind:
    def __init__(self):
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        # deterministic: smaller id becomes root
        lo, hi = sorted((ra, rb))
        self.parent[hi] = lo


def _shingles(source) -> set[str]:
    toks = tokenize(f"{source.title} {source.metadata.get('excerpt', '')}")
    return set(toks)


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def resolve_independence(sources) -> dict:
    """Return a dict with per-source resolved group and aggregate counts.

    Deterministic: sources are processed in sorted(source_id) order and the
    union-find always roots at the lexicographically smaller id.
    """
    sources = sorted(sources, key=lambda s: s.source_id)
    uf = _UnionFind()
    for s in sources:
        uf.find(s.source_id)

    # layer 1: exact content hash
    by_hash: dict[str, list[str]] = defaultdict(list)
    for s in sources:
        by_hash[s.content_hash].append(s.source_id)
    for ids in by_hash.values():
        for other in ids[1:]:
            uf.union(ids[0], other)

    # layer 2: declared independence group
    by_group: dict[str, list[str]] = defaultdict(list)
    for s in sources:
        if s.independence_group:
            by_group[s.independence_group].append(s.source_id)
    for ids in by_group.values():
        for other in ids[1:]:
            uf.union(ids[0], other)

    # layer 3: near-duplicate shingles via MinHash-LSH. We only compute exact
    # jaccard for LSH-candidate pairs, keeping this near-linear at scale.
    # Token-less titles produce no signature and are never near-duplicates.
    shingles = {s.source_id: _shingles(s) for s in sources}
    signatures = {sid: sig for sid, sh in shingles.items()
                  if (sig := _minhash_signature(sh)) is not None}
    for a, b in sorted(_lsh_candidate_pairs(signatures)):
        if uf.find(a) == uf.find(b):
            continue
        if jaccard(shingles[a], shingles[b]) >= NEAR_DUP_JACCARD:
            uf.union(a, b)

    resolved = {s.source_id: uf.find(s.source_id) for s in sources}
    groups = set(resolved.values())
    unique_hashes = len(by_hash)
    duplicate_pairs = [
        s.source_id for s in sources
        if resolved[s.source_id] != s.source_id
    ]
    return {
        "resolved_group": resolved,
        "raw_source_count": len(sources),
        "deduplicated_source_count": unique_hashes,
        "independent_source_count": len(groups),
        "duplicate_source_ids": sorted(duplicate_pairs),
    }


def independent_sources_for(source_ids, resolved_group: dict) -> int:
    """Number of *independent* sources among a set of source ids."""
    return len({resolved_group.get(sid, sid) for sid in source_ids})

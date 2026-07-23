"""Existing-industry comparison (spec §12).

A candidate cluster is compared against a versioned taxonomy of known
industries. High similarity => the cluster is likely just a rebranding of a
mature industry (EXISTING_INDUSTRY_VARIANT), not a genuinely new one.

Industry profiles are built from the taxonomy's capabilities/synonyms/
description only — never from the runtime corpus — so this stays a fair,
leakage-free reference (the taxonomy is versioned per §19).
"""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

from .features import tokenize, build_entity_documents
from .errors import AuroraError


class Taxonomy:
    def __init__(self, data: dict):
        self.version = data.get("version")
        if not self.version:
            raise AuroraError("TAXONOMY_VERSION_MISSING", "taxonomy has no version", stage="taxonomy")
        self.industries = data["industries"]
        self._vectors = {ind["id"]: self._profile_vector(ind) for ind in self.industries}

    @classmethod
    def load(cls, path: str | Path) -> "Taxonomy":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    @staticmethod
    def _profile_vector(ind: dict) -> dict[str, float]:
        text = " ".join([
            ind.get("name", ""),
            " ".join(ind.get("synonyms", [])),
            ind.get("description", ""),
            " ".join(ind.get("capabilities", [])),
            " ".join(ind.get("upstream", [])),
            " ".join(ind.get("downstream", [])),
        ])
        c = Counter(tokenize(text))
        norm = math.sqrt(sum(v * v for v in c.values())) or 1.0
        return {t: v / norm for t, v in c.items()}

    def cluster_vector(self, cluster_entity_ids, entities, observations) -> dict[str, float]:
        docs = build_entity_documents(entities, observations)
        bag = Counter()
        idset = set(cluster_entity_ids)
        for eid in idset:
            bag.update(tokenize(docs.get(eid, "")))
        norm = math.sqrt(sum(v * v for v in bag.values())) or 1.0
        return {t: v / norm for t, v in bag.items()}

    def best_match(self, cluster_vec: dict[str, float]) -> dict:
        """Return best-matching industry and full ranked similarities."""
        sims = []
        for ind in self.industries:
            v = self._vectors[ind["id"]]
            common = set(cluster_vec) & set(v)
            dot = sum(cluster_vec[t] * v[t] for t in common)
            sims.append((ind["id"], ind["name"], dot))
        sims.sort(key=lambda x: (-x[2], x[0]))
        best_id, best_name, best_sim = sims[0]
        # detect straddle: close to two industries (new cross-domain field)
        straddle = len(sims) > 1 and sims[1][2] >= 0.5 * best_sim and best_sim > 0.2
        return {
            "best_industry_id": best_id,
            "best_industry_name": best_name,
            "similarity": round(best_sim, 4),
            "ranked": [{"id": i, "name": n, "similarity": round(s, 4)} for i, n, s in sims[:5]],
            "straddles_two": straddle,
        }

"""Immutable snapshots + research-run records (spec §22).

Snapshots and runs are content-addressed and never mutated in place. Persistence
is plain JSON on disk (deterministic, diffable). SQLAlchemy/SQLite is the
intended production store and is tracked as PARTIAL in the self-audit.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .ids import content_hash
from .models import Source, Entity, Observation, to_dict


@dataclass
class Snapshot:
    snapshot_id: str
    created_at: str
    entities: list
    sources: list
    observations: list
    resolved_group: dict
    import_errors: list = field(default_factory=list)
    counts: dict = field(default_factory=dict)

    def input_manifest_hash(self) -> str:
        return content_hash(
            sorted(e.entity_id for e in self.entities),
            sorted(s.source_id for s in self.sources),
            sorted(o.observation_id for o in self.observations),
        )


def make_snapshot(entities, sources, observations, resolved_group, import_errors, created_at) -> Snapshot:
    sid = content_hash(
        sorted(e.entity_id for e in entities),
        sorted(s.source_id for s in sources),
        sorted(o.observation_id for o in observations),
    )
    counts = {
        "entities": len(entities),
        "sources": len(sources),
        "observations": len(observations),
        "import_errors": len(import_errors),
    }
    return Snapshot(
        snapshot_id=f"snap_{sid}", created_at=created_at, entities=entities, sources=sources,
        observations=observations, resolved_group=resolved_group, import_errors=import_errors, counts=counts,
    )


@dataclass
class ResearchRun:
    run_id: str
    snapshot_id: str
    cutoff_date: str | None
    engine_version: str
    feature_version: str
    taxonomy_version: str
    algorithm_config: dict
    scoring_config: dict
    created_at: str
    status: str
    input_manifest_hash: str
    result_manifest_hash: str
    hypotheses: list = field(default_factory=list)
    leakage_manifest: dict = field(default_factory=dict)
    stage_timings: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["hypotheses"] = [to_dict(h) if not isinstance(h, dict) else h for h in self.hypotheses]
        return d


def save_json(path: str | Path, obj) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    data = obj if isinstance(obj, (dict, list)) else (obj.to_dict() if hasattr(obj, "to_dict") else asdict(obj))
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")

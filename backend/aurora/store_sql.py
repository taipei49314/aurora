"""SQLAlchemy/SQLite persistence (spec §4).

The production persistence layer promised in ADR-0002. Snapshots persist as
normalized entity/source/observation rows; Research Runs and their hypotheses
persist with typed key columns plus JSON detail. Because all ids are
content-addressed and the engine is deterministic, a snapshot round-tripped
through SQLite reproduces the exact same run (verified in
``test_persistence.py``).

This module is OPTIONAL — it imports SQLAlchemy lazily so the pure-stdlib core
never depends on it.
"""
from __future__ import annotations

import json

from typing import Optional

from sqlalchemy import (create_engine, String, Float, Integer, JSON, ForeignKey, select)
from sqlalchemy.orm import (DeclarativeBase, Mapped, mapped_column, relationship, Session)

from .models import Source, Entity, Observation
from .store import Snapshot, make_snapshot, ResearchRun


class Base(DeclarativeBase):
    pass


class SnapshotRow(Base):
    __tablename__ = "snapshots"
    snapshot_id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[str] = mapped_column(String)
    counts: Mapped[dict] = mapped_column(JSON)
    resolved_group: Mapped[dict] = mapped_column(JSON)
    import_errors: Mapped[list] = mapped_column(JSON, default=list)


class EntityRow(Base):
    __tablename__ = "entities"
    entity_id: Mapped[str] = mapped_column(String, primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.snapshot_id"), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String)
    canonical_name: Mapped[str] = mapped_column(String)
    aliases: Mapped[list] = mapped_column(JSON)
    description: Mapped[str] = mapped_column(String)
    country: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)
    meta: Mapped[dict] = mapped_column(JSON)


class SourceRow(Base):
    __tablename__ = "sources"
    source_id: Mapped[str] = mapped_column(String, primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.snapshot_id"), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)  # full Source dict


class ObservationRow(Base):
    __tablename__ = "observations"
    observation_id: Mapped[str] = mapped_column(String, primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.snapshot_id"), primary_key=True)
    subject_entity: Mapped[str] = mapped_column(String, index=True)
    observation_type: Mapped[str] = mapped_column(String, index=True)
    observed_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)  # full Observation dict


class RunRow(Base):
    __tablename__ = "research_runs"
    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String, index=True)
    cutoff_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    engine_version: Mapped[str] = mapped_column(String)
    result_manifest_hash: Mapped[str] = mapped_column(String)
    input_manifest_hash: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)  # full run.to_dict()


def make_engine(url: str = "sqlite:///aurora.db"):
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return engine


# --- snapshot persistence (immutable: insert-or-ignore by content id) ---

def save_snapshot(engine, snap: Snapshot) -> None:
    with Session(engine) as s:
        if s.get(SnapshotRow, snap.snapshot_id):
            return  # content-addressed & immutable: already stored
        s.add(SnapshotRow(snapshot_id=snap.snapshot_id, created_at=snap.created_at,
                          counts=snap.counts, resolved_group=snap.resolved_group,
                          import_errors=snap.import_errors))
        for e in snap.entities:
            # external_ids is first-class on Entity; fold into meta for the row schema
            meta = dict(e.metadata or {})
            if e.external_ids:
                meta["external_ids"] = list(e.external_ids)
            s.add(EntityRow(entity_id=e.entity_id, snapshot_id=snap.snapshot_id,
                            entity_type=e.entity_type, canonical_name=e.canonical_name,
                            aliases=e.aliases, description=e.description, country=e.country,
                            created_at=e.created_at, meta=meta))
        for src in snap.sources:
            s.add(SourceRow(source_id=src.source_id, snapshot_id=snap.snapshot_id,
                            payload=json.loads(json.dumps(src.__dict__))))
        for o in snap.observations:
            s.add(ObservationRow(observation_id=o.observation_id, snapshot_id=snap.snapshot_id,
                                 subject_entity=o.subject_entity, observation_type=o.observation_type,
                                 observed_at=o.observed_at, payload=json.loads(json.dumps(o.__dict__))))
        s.commit()


def load_snapshot(engine, snapshot_id: str) -> Snapshot:
    with Session(engine) as s:
        row = s.get(SnapshotRow, snapshot_id)
        if not row:
            raise KeyError(snapshot_id)
        entities = []
        for r in s.scalars(select(EntityRow).where(EntityRow.snapshot_id == snapshot_id)):
            meta = dict(r.meta or {})
            ext = list(meta.pop("external_ids", None) or [])
            entities.append(Entity(
                entity_id=r.entity_id, entity_type=r.entity_type,
                canonical_name=r.canonical_name, aliases=list(r.aliases),
                description=r.description, country=r.country, created_at=r.created_at,
                external_ids=ext, metadata=meta,
            ))
        sources = [Source(**r.payload)
                   for r in s.scalars(select(SourceRow).where(SourceRow.snapshot_id == snapshot_id))]
        observations = [Observation(**r.payload)
                        for r in s.scalars(select(ObservationRow).where(ObservationRow.snapshot_id == snapshot_id))]
        snap = make_snapshot(sorted(entities, key=lambda e: e.entity_id),
                             sorted(sources, key=lambda x: x.source_id),
                             sorted(observations, key=lambda o: o.observation_id),
                             row.resolved_group, row.import_errors, row.created_at)
        snap.counts = row.counts
        return snap


def save_run(engine, run: ResearchRun) -> None:
    with Session(engine) as s:
        if s.get(RunRow, run.run_id):
            return  # runs are immutable
        s.add(RunRow(run_id=run.run_id, snapshot_id=run.snapshot_id, cutoff_date=run.cutoff_date,
                     engine_version=run.engine_version, result_manifest_hash=run.result_manifest_hash,
                     input_manifest_hash=run.input_manifest_hash, payload=run.to_dict()))
        s.commit()


def load_run_payload(engine, run_id: str) -> dict:
    with Session(engine) as s:
        row = s.get(RunRow, run_id)
        if not row:
            raise KeyError(run_id)
        return row.payload

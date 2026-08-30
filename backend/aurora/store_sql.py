"""SQLAlchemy/SQLite persistence (spec §4).

The production persistence layer promised in ADR-0002. Snapshots persist as
normalized entity/source/observation/document rows; Research Runs and their
hypotheses persist with typed key columns plus JSON detail. Snapshot ids retain
their stable row-id-set semantics, while re-saving an id verifies the complete
input manifest and pipeline-material snapshot metadata before accepting it.
Round-tripped inputs therefore reproduce the same deterministic run (verified
in ``test_persistence.py``).

This module is OPTIONAL and is not imported by the pure-stdlib core, so engine
use without the SQL store does not depend on SQLAlchemy or Alembic. Persistent
store databases are migration-managed; ephemeral SQLite uses metadata setup on
its live connection.
"""
from __future__ import annotations

import json

from pathlib import Path
from typing import Optional

from sqlalchemy import (
    create_engine,
    String,
    Float,
    Integer,
    JSON,
    ForeignKey,
    inspect,
    select,
)
from sqlalchemy.orm import (DeclarativeBase, Mapped, mapped_column, relationship, Session)

from .models import Source, Entity, Observation, Document
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


class DocumentRow(Base):
    __tablename__ = "documents"
    document_id: Mapped[str] = mapped_column(String, primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.snapshot_id"), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)  # full Document dict


class RunRow(Base):
    __tablename__ = "research_runs"
    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String, index=True)
    cutoff_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    engine_version: Mapped[str] = mapped_column(String)
    result_manifest_hash: Mapped[str] = mapped_column(String)
    input_manifest_hash: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)  # full run.to_dict()


_LEGACY_SCHEMA_REVISION = "ec328ff867b1"


def _is_ephemeral_sqlite(engine) -> bool:
    """Return whether schema setup must stay on the engine's live connection."""
    if engine.dialect.name != "sqlite":
        return False
    database = engine.url.database
    return (
        database in (None, "", ":memory:")
        or engine.url.query.get("mode") == "memory"
    )


def _alembic_config(connection):
    """Build an Alembic config pinned to the already-selected connection."""
    from alembic.config import Config

    package_dir = Path(__file__).resolve().parent
    config = Config(str(package_dir / "alembic.ini"))
    config.set_main_option(
        "script_location", str(package_dir / "migrations")
    )
    config.attributes["connection"] = connection
    return config


def _semantic_schema_differences(connection):
    """Compare an unmanaged database to the current SQLAlchemy metadata."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    migration_context = MigrationContext.configure(
        connection,
        opts={
            "compare_type": True,
            "compare_server_default": True,
        },
    )
    return compare_metadata(migration_context, Base.metadata)


def _is_exact_legacy_schema(differences) -> bool:
    """Recognize the old five-table schema by its sole semantic delta."""
    if len(differences) != 1:
        return False
    difference = differences[0]
    if not isinstance(difference, tuple) or len(difference) != 2:
        return False
    operation, table = difference
    return (
        operation == "add_table"
        and getattr(table, "name", None) == "documents"
        and getattr(table, "schema", None) is None
    )


def _difference_operations(differences) -> str:
    """Return stable operation names without Alembic object's repr output."""
    operations = set()

    def collect(items) -> None:
        for item in items:
            if isinstance(item, list):
                collect(item)
            elif isinstance(item, tuple) and item:
                operations.add(str(item[0]))
            else:
                operations.add("unknown")

    collect(differences)
    return ", ".join(sorted(operations)) or "unknown"


def _migrate_persistent_database(engine) -> None:
    """Upgrade or conservatively adopt a persistent database schema."""
    from alembic import command

    try:
        with engine.begin() as connection:
            inspector = inspect(connection)
            table_names = set(inspector.get_table_names())
            config = _alembic_config(connection)

            if not table_names or "alembic_version" in table_names:
                command.upgrade(config, "head")
                return

            differences = _semantic_schema_differences(connection)
            if not differences:
                command.stamp(config, "head")
                return
            if _is_exact_legacy_schema(differences):
                command.stamp(config, _LEGACY_SCHEMA_REVISION)
                command.upgrade(config, "head")
                return

            operations = _difference_operations(differences)
            raise RuntimeError(
                "refusing to adopt unmanaged database: schema does not "
                "exactly match Aurora's current or legacy schema "
                f"(semantic differences: {operations})"
            )
    except Exception:
        engine.dispose()
        raise


def make_engine(url: str = "sqlite:///aurora.db"):
    engine = create_engine(url)
    if _is_ephemeral_sqlite(engine):
        Base.metadata.create_all(engine)
    else:
        _migrate_persistent_database(engine)
    return engine


# --- snapshot persistence (immutable: insert-or-verify by content id) ---


def _json_payload(value):
    """Return the JSON representation that SQLAlchemy will persist."""
    return json.loads(json.dumps(value))


def _snapshot_identity(snap: Snapshot) -> dict:
    """Return persisted fields that may affect snapshot or pipeline meaning."""
    return {
        "input_manifest_hash": snap.input_manifest_hash(),
        "resolved_group": _json_payload(snap.resolved_group),
        "import_errors": _json_payload(snap.import_errors),
        "counts": _json_payload(snap.counts),
    }


def _load_snapshot_from_session(s: Session, snapshot_id: str) -> Snapshot:
    """Reconstruct a snapshot without opening a second database session."""
    row = s.get(SnapshotRow, snapshot_id)
    if not row:
        raise KeyError(snapshot_id)
    entities = []
    for entity_row in s.scalars(
        select(EntityRow).where(EntityRow.snapshot_id == snapshot_id)
    ):
        meta = dict(entity_row.meta or {})
        external_ids = list(meta.pop("external_ids", None) or [])
        entities.append(Entity(
            entity_id=entity_row.entity_id,
            entity_type=entity_row.entity_type,
            canonical_name=entity_row.canonical_name,
            aliases=list(entity_row.aliases),
            description=entity_row.description,
            country=entity_row.country,
            created_at=entity_row.created_at,
            external_ids=external_ids,
            metadata=meta,
        ))
    sources = [
        Source(**source_row.payload)
        for source_row in s.scalars(
            select(SourceRow).where(SourceRow.snapshot_id == snapshot_id)
        )
    ]
    observations = [
        Observation(**observation_row.payload)
        for observation_row in s.scalars(
            select(ObservationRow).where(ObservationRow.snapshot_id == snapshot_id)
        )
    ]
    documents = [
        Document(**document_row.payload)
        for document_row in s.scalars(
            select(DocumentRow).where(DocumentRow.snapshot_id == snapshot_id)
        )
    ]
    snap = make_snapshot(
        sorted(entities, key=lambda entity: entity.entity_id),
        sorted(sources, key=lambda source: source.source_id),
        sorted(observations, key=lambda observation: observation.observation_id),
        row.resolved_group,
        row.import_errors,
        row.created_at,
        documents=sorted(documents, key=lambda document: document.document_id),
    )
    if snap.snapshot_id != snapshot_id:
        raise ValueError(
            "snapshot integrity check failed: "
            f"requested {snapshot_id}, reconstructed {snap.snapshot_id}"
        )
    snap.counts = row.counts
    return snap


def save_snapshot(engine, snap: Snapshot) -> None:
    with Session(engine) as s:
        if s.get(SnapshotRow, snap.snapshot_id):
            # Snapshots written before DocumentRow existed already have the
            # document ids folded into snapshot_id/counts, but no document rows.
            # Re-saving the original snapshot backfills only those missing rows.
            stored_documents = {
                row.document_id: row
                for row in s.scalars(
                    select(DocumentRow).where(DocumentRow.snapshot_id == snap.snapshot_id)
                )
            }
            for document in snap.documents or []:
                payload = _json_payload(
                    document if isinstance(document, dict) else document.__dict__
                )
                document_id = payload["document_id"]
                stored = stored_documents.get(document_id)
                if stored is None:
                    stored = DocumentRow(
                        document_id=document_id,
                        snapshot_id=snap.snapshot_id,
                        payload=payload,
                    )
                    s.add(stored)
                    stored_documents[document_id] = stored
            # Flush backfilled document rows before reconstructing through this
            # same session. This is important for transactional correctness and
            # for in-memory SQLite, where another session may use another DB.
            s.flush()
            stored_snapshot = _load_snapshot_from_session(s, snap.snapshot_id)
            if _snapshot_identity(stored_snapshot) != _snapshot_identity(snap):
                raise ValueError(
                    "snapshot identity conflict for "
                    f"{snap.snapshot_id}"
                )
            s.commit()
            return  # stable id was verified; existing rows remain insert-once
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
                            payload=_json_payload(src.__dict__)))
        for o in snap.observations:
            s.add(ObservationRow(observation_id=o.observation_id, snapshot_id=snap.snapshot_id,
                                 subject_entity=o.subject_entity, observation_type=o.observation_type,
                                 observed_at=o.observed_at, payload=_json_payload(o.__dict__)))
        for document in snap.documents or []:
            payload = _json_payload(
                document if isinstance(document, dict) else document.__dict__
            )
            s.add(DocumentRow(document_id=payload["document_id"], snapshot_id=snap.snapshot_id,
                              payload=payload))
        s.commit()


def load_snapshot(engine, snapshot_id: str) -> Snapshot:
    with Session(engine) as s:
        return _load_snapshot_from_session(s, snapshot_id)


def _substantive_run_payload(payload: dict) -> dict:
    """Normalize a run payload while excluding explicitly volatile fields."""
    substantive = _json_payload(payload)
    substantive.pop("created_at", None)
    substantive.pop("stage_timings", None)
    return substantive


def save_run(engine, run: ResearchRun) -> None:
    with Session(engine) as s:
        existing = s.get(RunRow, run.run_id)
        if existing:
            typed_identity_matches = (
                existing.snapshot_id == run.snapshot_id
                and existing.cutoff_date == run.cutoff_date
                and existing.engine_version == run.engine_version
                and existing.result_manifest_hash == run.result_manifest_hash
                and existing.input_manifest_hash == run.input_manifest_hash
            )
            payload_identity_matches = (
                _substantive_run_payload(existing.payload)
                == _substantive_run_payload(run.to_dict())
            )
            if not typed_identity_matches or not payload_identity_matches:
                raise ValueError(f"run identity conflict for {run.run_id}")
            return
        s.add(RunRow(run_id=run.run_id, snapshot_id=run.snapshot_id, cutoff_date=run.cutoff_date,
                     engine_version=run.engine_version, result_manifest_hash=run.result_manifest_hash,
                     input_manifest_hash=run.input_manifest_hash,
                     payload=_json_payload(run.to_dict())))
        s.commit()


def load_run_payload(engine, run_id: str) -> dict:
    with Session(engine) as s:
        row = s.get(RunRow, run_id)
        if not row:
            raise KeyError(run_id)
        return row.payload

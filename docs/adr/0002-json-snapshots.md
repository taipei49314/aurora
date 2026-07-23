# ADR 0002 — JSON snapshots instead of SQLite (for the MVP slice)

## Status
Accepted for the MVP; SQLite/SQLAlchemy/Alembic planned.

## Context
Spec §4 lists SQLite + SQLAlchemy + Alembic. The immutable, content-addressed
nature of snapshots and runs (§22) means the data is effectively write-once and
diff-friendly.

## Decision
Persist snapshots and Research Runs as **content-addressed JSON** (`store.py`),
with all ids derived from content hashes. The in-memory dataclass model is the
source of truth during a run.

## Consequences
- **+** Deterministic, human-diffable artifacts; trivial reproducibility checks
  (compare `result_manifest_hash`).
- **+** No schema migrations to run for the demo; zero DB setup.
- **−** No indexed queries / concurrent writers. Fine for single-user MVP.
- **Follow-up**: add a SQLAlchemy store implementing the same `Snapshot` /
  `ResearchRun` interfaces; Alembic migrations; keep JSON export for audit.
  Tracked as PARTIAL in `self-audit.md`.

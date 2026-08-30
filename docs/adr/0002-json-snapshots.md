# ADR 0002 — JSON snapshots for the MVP and audit artifacts

## Status
Accepted for the MVP; amended after SQLite/SQLAlchemy/Alembic implementation.

## Context
Spec §4 lists SQLite + SQLAlchemy + Alembic. Stable ids, full manifest hashes,
and the insert-once persistence convention (§22) make stored data effectively
write-once and diff-friendly, although the in-memory dataclasses are not frozen.

## Decision
Persist snapshots and Research Runs as deterministic JSON (`store.py`).
Generated record ids remain content-derived, while `snapshot_id` deliberately
identifies the sorted row-id set for backward compatibility. The separate
versioned `input_manifest_hash` covers every normalized entity, source,
observation, and document payload; `run_id` includes both identities. The
in-memory dataclass model is the source of truth during a run. Keep JSON as the
portable audit/export format; use the SQLAlchemy store (`store_sql.py`) and
Alembic migrations for indexed SQLite persistence.

Persistent `make_engine` databases are migration-managed from creation.
Ephemeral in-memory SQLite keeps `create_all` because a separate Alembic
connection would lose the database. For pre-existing unmanaged files, adoption
is allowed only when Alembic's semantic metadata comparison matches the current
six-table schema exactly, or the legacy five-table schema differs only by the
missing `documents` table; any other difference fails closed.

## Consequences
- **+** Deterministic, human-diffable artifacts; trivial reproducibility checks
  (compare `result_manifest_hash`).
- **+** No schema migrations to run for the demo; zero DB setup.
- **−** JSON alone has no indexed queries / concurrent writers. Fine for the
  stdlib-only and portable audit path.
- **−** `snapshot_id` alone is a membership identity, not a full-content digest;
  audit or compare `input_manifest_hash` as well. SQL insert-or-verify rejects a
  reused snapshot id when the full manifest or pipeline metadata differs.
- **Follow-up (implemented 2026-07-23)**: the SQLAlchemy store implements the
  same `Snapshot` / `ResearchRun` boundary. Alembic now creates six tables,
  including complete document payloads, and round-trip tests require identical
  snapshot/input-manifest identities and result hashes. The 2026-08-30 migration
  and bootstrap path safely adopt exact application-created schemas and reject
  mismatches. JSON export remains available for audit.

"""SQLite persistence round-trip + cross-DB determinism (spec §4, §22, §29)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest as _pytest
pytestmark = _pytest.mark.integration

import pytest

from aurora import import_package, run_pipeline, DEFAULT_CONFIG

sqlalchemy = pytest.importorskip("sqlalchemy")
from aurora import store_sql  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
BASE_REVISION = "ec328ff867b1"
HEAD_REVISION = "a7c5d9e1f203"


def _document_snapshot():
    package = json.loads(
        (ROOT / "examples" / "real_mini_package.json").read_text(encoding="utf-8")
    )
    return import_package(package)


def _alembic_config(database, monkeypatch, config_path=None):
    pytest.importorskip("alembic")
    from alembic import command
    from alembic.config import Config

    url = f"sqlite:///{database.as_posix()}"
    config = Config(str(
        config_path or ROOT / "backend" / "aurora" / "alembic.ini"
    ))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.delenv("AURORA_DB_URL", raising=False)
    return command, config, url


def _database_revision(engine):
    with engine.connect() as connection:
        return connection.execute(
            sqlalchemy.text("SELECT version_num FROM alembic_version")
        ).scalar_one()


def test_in_memory_make_engine_keeps_ephemeral_metadata_setup():
    engine = store_sql.make_engine("sqlite:///:memory:")

    table_names = set(sqlalchemy.inspect(engine).get_table_names())
    assert set(store_sql.Base.metadata.tables) <= table_names
    assert "alembic_version" not in table_names


def test_checkout_alembic_config_uses_packaged_migration_chain(
    tmp_path, monkeypatch
):
    database = tmp_path / "checkout-cli.db"
    command, config, url = _alembic_config(
        database, monkeypatch, ROOT / "backend" / "alembic.ini"
    )

    command.upgrade(config, "head")

    engine = sqlalchemy.create_engine(url)
    assert _database_revision(engine) == HEAD_REVISION
    assert set(store_sql.Base.metadata.tables) <= set(
        sqlalchemy.inspect(engine).get_table_names()
    )


def test_make_engine_migrates_empty_persistent_database_to_head(
    tmp_path, monkeypatch
):
    database = tmp_path / "managed.db"
    wrong_database = tmp_path / "ambient-wrong.db"
    url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv(
        "AURORA_DB_URL", f"sqlite:///{wrong_database.as_posix()}"
    )

    engine = store_sql.make_engine(url)

    assert _database_revision(engine) == HEAD_REVISION
    table_names = set(sqlalchemy.inspect(engine).get_table_names())
    assert set(store_sql.Base.metadata.tables) <= table_names
    assert "alembic_version" in table_names
    assert not wrong_database.exists()


def test_make_engine_adopts_exact_current_unmanaged_schema_and_preserves_rows(
    tmp_path,
):
    database = tmp_path / "current-unmanaged.db"
    url = f"sqlite:///{database.as_posix()}"
    raw_engine = sqlalchemy.create_engine(url)
    store_sql.Base.metadata.create_all(raw_engine)
    snapshot = _document_snapshot()
    store_sql.save_snapshot(raw_engine, snapshot)
    assert "alembic_version" not in sqlalchemy.inspect(raw_engine).get_table_names()

    engine = store_sql.make_engine(url)

    assert _database_revision(engine) == HEAD_REVISION
    loaded = store_sql.load_snapshot(engine, snapshot.snapshot_id)
    assert loaded.input_manifest_hash() == snapshot.input_manifest_hash()
    assert loaded.documents == sorted(
        snapshot.documents, key=lambda document: document.document_id
    )


def test_make_engine_adopts_exact_legacy_unmanaged_schema_then_migrates(
    tmp_path,
):
    database = tmp_path / "legacy-unmanaged.db"
    url = f"sqlite:///{database.as_posix()}"
    raw_engine = sqlalchemy.create_engine(url)
    legacy_tables = [
        table
        for table in store_sql.Base.metadata.sorted_tables
        if table.name != "documents"
    ]
    store_sql.Base.metadata.create_all(raw_engine, tables=legacy_tables)
    sentinel_id = "legacy-snapshot"
    with raw_engine.begin() as connection:
        connection.execute(
            store_sql.SnapshotRow.__table__.insert().values(
                snapshot_id=sentinel_id,
                created_at="2026-08-30T00:00:00+00:00",
                counts={},
                resolved_group={},
                import_errors=[],
            )
        )

    engine = store_sql.make_engine(url)

    assert _database_revision(engine) == HEAD_REVISION
    assert "documents" in sqlalchemy.inspect(engine).get_table_names()
    with sqlalchemy.orm.Session(engine) as session:
        assert session.get(store_sql.SnapshotRow, sentinel_id) is not None


def test_make_engine_refuses_malformed_unmanaged_schema_without_changes(
    tmp_path,
):
    database = tmp_path / "malformed-unmanaged.db"
    url = f"sqlite:///{database.as_posix()}"
    raw_engine = sqlalchemy.create_engine(url)
    store_sql.Base.metadata.create_all(raw_engine)
    with raw_engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE unexpected_data (id INTEGER PRIMARY KEY, value TEXT)"
        )
        connection.exec_driver_sql(
            "INSERT INTO unexpected_data (id, value) VALUES (1, 'preserve-me')"
        )
    before_tables = set(sqlalchemy.inspect(raw_engine).get_table_names())

    with pytest.raises(
        RuntimeError, match="refusing to adopt unmanaged database"
    ):
        store_sql.make_engine(url)

    inspector = sqlalchemy.inspect(raw_engine)
    assert set(inspector.get_table_names()) == before_tables
    assert "alembic_version" not in inspector.get_table_names()
    with raw_engine.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT value FROM unexpected_data WHERE id = 1"
        ).scalar_one() == "preserve-me"


def test_snapshot_roundtrip_preserves_content(snapshot):
    engine = store_sql.make_engine("sqlite:///:memory:")
    store_sql.save_snapshot(engine, snapshot)
    loaded = store_sql.load_snapshot(engine, snapshot.snapshot_id)
    assert loaded.snapshot_id == snapshot.snapshot_id
    assert loaded.input_manifest_hash() == snapshot.input_manifest_hash()
    assert loaded.counts["observations"] == snapshot.counts["observations"]


def test_snapshot_roundtrip_preserves_complete_documents():
    snapshot = _document_snapshot()
    assert snapshot.documents
    engine = store_sql.make_engine("sqlite:///:memory:")

    store_sql.save_snapshot(engine, snapshot)
    loaded = store_sql.load_snapshot(engine, snapshot.snapshot_id)

    expected = {d.document_id: d.__dict__ for d in snapshot.documents}
    actual = {d.document_id: d.__dict__ for d in loaded.documents}
    assert actual == expected
    assert loaded.snapshot_id == snapshot.snapshot_id
    assert loaded.input_manifest_hash() == snapshot.input_manifest_hash()
    assert loaded.counts == snapshot.counts


def test_resave_backfills_missing_document_rows_idempotently():
    snapshot = _document_snapshot()
    engine = store_sql.make_engine("sqlite:///:memory:")
    store_sql.save_snapshot(engine, snapshot)

    with sqlalchemy.orm.Session(engine) as session:
        session.query(store_sql.DocumentRow).filter_by(
            snapshot_id=snapshot.snapshot_id
        ).delete()
        session.commit()
        assert session.get(store_sql.SnapshotRow, snapshot.snapshot_id) is not None

    store_sql.save_snapshot(engine, copy.deepcopy(snapshot))
    store_sql.save_snapshot(engine, snapshot)

    with sqlalchemy.orm.Session(engine) as session:
        rows = session.query(store_sql.DocumentRow).filter_by(
            snapshot_id=snapshot.snapshot_id
        ).all()
        assert len(rows) == len(snapshot.documents)
        assert {row.document_id: row.payload for row in rows} == {
            document.document_id: document.__dict__ for document in snapshot.documents
        }
    loaded = store_sql.load_snapshot(engine, snapshot.snapshot_id)
    assert loaded.input_manifest_hash() == snapshot.input_manifest_hash()


@pytest.mark.parametrize(
    ("collection", "attribute"),
    [
        ("documents", "text"),
        ("entities", "description"),
        ("sources", "title"),
        ("observations", "text_excerpt"),
    ],
)
def test_resave_rejects_same_row_ids_with_changed_payload(collection, attribute):
    snapshot = _document_snapshot()
    changed = copy.deepcopy(snapshot)
    record = getattr(changed, collection)[0]
    setattr(record, attribute, f"{getattr(record, attribute)} [changed]")
    assert changed.snapshot_id == snapshot.snapshot_id
    assert changed.input_manifest_hash() != snapshot.input_manifest_hash()
    engine = store_sql.make_engine("sqlite:///:memory:")
    store_sql.save_snapshot(engine, snapshot)

    with pytest.raises(ValueError, match="snapshot identity conflict"):
        store_sql.save_snapshot(engine, changed)

    loaded = store_sql.load_snapshot(engine, snapshot.snapshot_id)
    assert loaded.input_manifest_hash() == snapshot.input_manifest_hash()


@pytest.mark.parametrize("field", ["resolved_group", "import_errors", "counts"])
def test_resave_rejects_changed_pipeline_material_snapshot_metadata(field):
    snapshot = _document_snapshot()
    changed = copy.deepcopy(snapshot)
    if field == "resolved_group":
        changed.resolved_group["collision_test"] = ["changed"]
    elif field == "import_errors":
        changed.import_errors.append({"collision_test": "changed"})
    else:
        changed.counts["collision_test"] = 1
    assert changed.snapshot_id == snapshot.snapshot_id
    assert changed.input_manifest_hash() == snapshot.input_manifest_hash()
    engine = store_sql.make_engine("sqlite:///:memory:")
    store_sql.save_snapshot(engine, snapshot)

    with pytest.raises(ValueError, match="snapshot identity conflict"):
        store_sql.save_snapshot(engine, changed)


def test_load_snapshot_fails_closed_when_document_rows_are_missing():
    snapshot = _document_snapshot()
    engine = store_sql.make_engine("sqlite:///:memory:")
    store_sql.save_snapshot(engine, snapshot)

    with sqlalchemy.orm.Session(engine) as session:
        session.query(store_sql.DocumentRow).filter_by(
            snapshot_id=snapshot.snapshot_id,
            document_id=snapshot.documents[0].document_id,
        ).delete()
        session.commit()

    with pytest.raises(ValueError, match="snapshot integrity check failed"):
        store_sql.load_snapshot(engine, snapshot.snapshot_id)


def test_run_is_reproducible_across_db_boundary(snapshot, taxonomy):
    engine = store_sql.make_engine("sqlite:///:memory:")
    store_sql.save_snapshot(engine, snapshot)
    loaded = store_sql.load_snapshot(engine, snapshot.snapshot_id)
    in_memory = run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG)
    from_db = run_pipeline(loaded, taxonomy, DEFAULT_CONFIG)
    # same content in -> byte-identical result manifest out
    assert from_db.result_manifest_hash == in_memory.result_manifest_hash


def test_document_payload_changes_manifest_and_run_id_but_not_snapshot_id(taxonomy):
    snapshot = _document_snapshot()
    changed = copy.deepcopy(snapshot)
    changed.documents[0].text += " [changed]"

    assert changed.snapshot_id == snapshot.snapshot_id
    assert changed.input_manifest_hash() != snapshot.input_manifest_hash()

    original_run = run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG)
    changed_run = run_pipeline(changed, taxonomy, DEFAULT_CONFIG)
    assert changed_run.input_manifest_hash != original_run.input_manifest_hash
    assert changed_run.run_id != original_run.run_id


def test_snapshot_save_is_idempotent(snapshot):
    engine = store_sql.make_engine("sqlite:///:memory:")
    store_sql.save_snapshot(engine, snapshot)
    store_sql.save_snapshot(engine, snapshot)  # verified identical re-save is a no-op
    with sqlalchemy.orm.Session(engine) as s:
        n = s.query(store_sql.EntityRow).filter_by(snapshot_id=snapshot.snapshot_id).count()
    assert n == snapshot.counts["entities"]


def test_run_persistence_roundtrip(snapshot, taxonomy):
    engine = store_sql.make_engine("sqlite:///:memory:")
    run = run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG)
    store_sql.save_run(engine, run)
    payload = store_sql.load_run_payload(engine, run.run_id)
    assert payload["result_manifest_hash"] == run.result_manifest_hash
    assert len(payload["hypotheses"]) == len(run.hypotheses)


def test_save_run_allows_same_identity_with_new_volatile_fields(run):
    engine = store_sql.make_engine("sqlite:///:memory:")
    original = copy.deepcopy(run)
    repeated = copy.deepcopy(run)
    repeated.created_at = "2099-01-01T00:00:00+00:00"
    repeated.stage_timings = {"volatile_rerun": 123.0}

    store_sql.save_run(engine, original)
    store_sql.save_run(engine, repeated)

    assert store_sql.load_run_payload(engine, run.run_id) == original.to_dict()
    with sqlalchemy.orm.Session(engine) as session:
        assert session.query(store_sql.RunRow).count() == 1


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("status", "FAILED"),
        ("input_manifest_hash", "v2:conflicting-input"),
        ("result_manifest_hash", "conflicting-result"),
    ],
)
def test_save_run_rejects_substantive_same_id_conflict(run, attribute, value):
    engine = store_sql.make_engine("sqlite:///:memory:")
    original = copy.deepcopy(run)
    conflicting = copy.deepcopy(run)
    setattr(conflicting, attribute, value)
    assert conflicting.run_id == original.run_id
    store_sql.save_run(engine, original)

    with pytest.raises(ValueError, match="run identity conflict"):
        store_sql.save_run(engine, conflicting)

    assert store_sql.load_run_payload(engine, run.run_id) == original.to_dict()


def test_alembic_direct_upgrade_adds_documents_table(tmp_path, monkeypatch):
    database = tmp_path / "migration.db"
    command, config, url = _alembic_config(database, monkeypatch)

    command.upgrade(config, BASE_REVISION)
    engine = sqlalchemy.create_engine(url)
    assert "documents" not in sqlalchemy.inspect(engine).get_table_names()

    command.upgrade(config, "head")
    assert _database_revision(engine) == HEAD_REVISION
    inspector = sqlalchemy.inspect(engine)
    assert "documents" in inspector.get_table_names()
    assert inspector.get_pk_constraint("documents")["constrained_columns"] == [
        "document_id", "snapshot_id",
    ]

    snapshot = _document_snapshot()
    store_sql.save_snapshot(engine, snapshot)
    loaded = store_sql.load_snapshot(engine, snapshot.snapshot_id)
    assert loaded.documents == sorted(snapshot.documents, key=lambda d: d.document_id)


def test_alembic_adopts_documents_precreated_by_legacy_app(tmp_path, monkeypatch):
    database = tmp_path / "adopt.db"
    command, config, url = _alembic_config(database, monkeypatch)
    command.upgrade(config, BASE_REVISION)

    engine = sqlalchemy.create_engine(url)
    assert _database_revision(engine) == BASE_REVISION
    assert "documents" not in sqlalchemy.inspect(engine).get_table_names()

    # Before make_engine became migration-managed, the app used create_all and
    # could create a newer model table while Alembic still reported base.
    store_sql.Base.metadata.create_all(engine)
    assert _database_revision(engine) == BASE_REVISION
    assert "documents" in sqlalchemy.inspect(engine).get_table_names()
    snapshot = _document_snapshot()
    store_sql.save_snapshot(engine, snapshot)
    with sqlalchemy.orm.Session(engine) as session:
        before = session.query(store_sql.DocumentRow).filter_by(
            snapshot_id=snapshot.snapshot_id
        ).count()

    command.upgrade(config, "head")

    assert _database_revision(engine) == HEAD_REVISION
    with sqlalchemy.orm.Session(engine) as session:
        after = session.query(store_sql.DocumentRow).filter_by(
            snapshot_id=snapshot.snapshot_id
        ).count()
    assert after == before == len(snapshot.documents)
    loaded = store_sql.load_snapshot(engine, snapshot.snapshot_id)
    assert loaded.input_manifest_hash() == snapshot.input_manifest_hash()


def test_alembic_refuses_incompatible_documents_table(tmp_path, monkeypatch):
    database = tmp_path / "incompatible.db"
    command, config, url = _alembic_config(database, monkeypatch)
    command.upgrade(config, BASE_REVISION)
    engine = sqlalchemy.create_engine(url)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE documents (
                document_id VARCHAR NOT NULL,
                snapshot_id VARCHAR NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (document_id, snapshot_id),
                FOREIGN KEY(snapshot_id) REFERENCES snapshots (snapshot_id)
            )
            """
        )

    with pytest.raises(RuntimeError, match="refusing to adopt incompatible documents table"):
        command.upgrade(config, "head")

    assert _database_revision(engine) == BASE_REVISION
    columns = sqlalchemy.inspect(engine).get_columns("documents")
    assert type(columns[2]["type"]).__name__ == "TEXT"

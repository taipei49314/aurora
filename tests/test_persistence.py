"""SQLite persistence round-trip + cross-DB determinism (spec §4, §22, §29)."""
from __future__ import annotations

import pytest as _pytest
pytestmark = _pytest.mark.integration

import pytest

from aurora import run_pipeline, DEFAULT_CONFIG

sqlalchemy = pytest.importorskip("sqlalchemy")
from aurora import store_sql  # noqa: E402


def test_snapshot_roundtrip_preserves_content(snapshot):
    engine = store_sql.make_engine("sqlite:///:memory:")
    store_sql.save_snapshot(engine, snapshot)
    loaded = store_sql.load_snapshot(engine, snapshot.snapshot_id)
    assert loaded.snapshot_id == snapshot.snapshot_id
    assert loaded.input_manifest_hash() == snapshot.input_manifest_hash()
    assert loaded.counts["observations"] == snapshot.counts["observations"]


def test_run_is_reproducible_across_db_boundary(snapshot, taxonomy):
    engine = store_sql.make_engine("sqlite:///:memory:")
    store_sql.save_snapshot(engine, snapshot)
    loaded = store_sql.load_snapshot(engine, snapshot.snapshot_id)
    in_memory = run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG)
    from_db = run_pipeline(loaded, taxonomy, DEFAULT_CONFIG)
    # same content in -> byte-identical result manifest out
    assert from_db.result_manifest_hash == in_memory.result_manifest_hash


def test_snapshot_save_is_idempotent(snapshot):
    engine = store_sql.make_engine("sqlite:///:memory:")
    store_sql.save_snapshot(engine, snapshot)
    store_sql.save_snapshot(engine, snapshot)  # immutable: second save is a no-op
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

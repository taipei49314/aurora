"""API surface tests (spec §26) — imports upload, exports round-trip, snapshot
persistence. Runs the real FastAPI app with TestClient; no network."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

fastapi = pytest.importorskip("fastapi", reason="API layer needs fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(api.app)


def test_health_and_snapshot_listing(client):
    assert client.get("/api/health").status_code == 200
    snaps = client.get("/api/snapshots").json()
    assert len(snaps) == 1 and snaps[0]["counts"]["entities"] > 0


def test_resolve_entity_by_name(client):
    ents = client.get("/api/entities?limit=50").json()
    assert ents
    name = ents[0]["canonical_name"]
    r = client.post("/api/resolve", json={"ref": name})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["canonical_name"] == name
    assert body["entity_id"] == ents[0]["entity_id"]


def test_resolve_unknown_returns_404(client):
    r = client.post("/api/resolve", json={"ref": "___no_such_entity_xyz___"})
    assert r.status_code == 404


def test_export_is_round_trippable_via_import_upload(client):
    pkg = client.get("/api/exports").json()
    assert set(pkg) == {"entities", "sources", "observations"}
    before = client.get("/api/snapshots").json()[0]["counts"]

    up = client.post(
        "/api/imports",
        files={"file": ("pkg.json", json.dumps(pkg).encode("utf-8"), "application/json")},
    )
    assert up.status_code == 200, up.text
    body = up.json()
    # re-importing the exported package reproduces the same corpus size
    assert body["counts"]["entities"] == before["entities"]
    assert body["counts"]["observations"] == before["observations"]


def test_import_upload_rejects_non_json(client):
    r = client.post("/api/imports", files={"file": ("x.bin", b"\xff\xfe not json", "application/octet-stream")})
    assert r.status_code == 400


def test_import_upload_rejects_non_object(client):
    r = client.post("/api/imports", files={"file": ("x.json", b"[1,2,3]", "application/json")})
    assert r.status_code == 400


def test_post_snapshots_persists_to_sqlite_and_is_idempotent(client, tmp_path, monkeypatch):
    store_sql = pytest.importorskip("aurora.store_sql", reason="needs sqlalchemy")
    # redirect the db file into tmp so the test never touches a real store
    real_make_engine = store_sql.make_engine
    monkeypatch.setattr(store_sql, "make_engine",
                        lambda url=None: real_make_engine(f"sqlite:///{tmp_path / 'aurora.db'}"))
    r1 = client.post("/api/snapshots")
    assert r1.status_code == 200, r1.text
    sid = r1.json()["snapshot_id"]
    r2 = client.post("/api/snapshots")   # content-addressed: second call is a no-op
    assert r2.status_code == 200 and r2.json()["snapshot_id"] == sid

    engine = store_sql.make_engine()
    back = store_sql.load_snapshot(engine, sid)
    assert len(back.entities) > 0 and len(back.observations) > 0

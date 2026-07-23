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


def test_entities_query_filter(client):
    ents = client.get("/api/entities?limit=50").json()
    assert ents
    name = ents[0]["canonical_name"]
    hit = client.get(f"/api/entities?q={name[: min(6, len(name))]}&limit=50").json()
    assert any(e["canonical_name"] == name for e in hit)
    miss = client.get("/api/entities?q=___no_match_xyz___&limit=50").json()
    assert miss == []


def test_stats_endpoint(client):
    r = client.get("/api/stats")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["entities_total"] > 0
    assert "reliability_tier_counts" in body
    assert "source_type_counts" in body
    assert "sources_total" in body
    assert "sources_with_family_id" in body
    assert "sources_with_event_date" in body
    assert "sources_with_event_id" in body
    assert "sources_with_outlet_domain" in body
    assert "sources_with_wire_id" in body
    assert "observations_with_event_id" in body
    assert "unique_event_ids" in body
    assert body["sources_total"] > 0
    assert isinstance(body["sources_with_family_id"], int)
    assert body["sources_with_family_id"] >= 0
    assert isinstance(body["sources_with_event_date"], int)
    assert body["sources_with_event_date"] >= 0
    assert isinstance(body["sources_with_outlet_domain"], int)
    assert body["sources_with_outlet_domain"] >= 0
    assert isinstance(body["unique_event_ids"], int)
    assert body["unique_event_ids"] >= 0
    assert sum(body["source_type_counts"].values()) == body["sources_total"]
    assert "engine" in body
    assert isinstance(body["reliability_tier_counts"], dict)
    assert sum(body["reliability_tier_counts"].values()) > 0


def test_sources_reliability_tier_filter(client):
    all_src = client.get("/api/sources?limit=500").json()
    assert all_src
    # Northstar corpus uses mixed tiers; every returned tier must match filter
    for tier in ("A", "B", "C", "D"):
        filtered = client.get(f"/api/sources?reliability_tier={tier}&limit=500").json()
        assert all(str(s.get("reliability_tier", "C")).upper() == tier for s in filtered)
        # filter should not invent rows
        assert len(filtered) <= len(all_src)
    multi = client.get("/api/sources?reliability_tier=A,B&limit=500").json()
    assert all(str(s.get("reliability_tier", "C")).upper() in {"A", "B"} for s in multi)
    bad = client.get("/api/sources?reliability_tier=Z")
    assert bad.status_code == 422


def test_sources_source_type_filter(client):
    all_src = client.get("/api/sources?limit=500").json()
    assert all_src
    st = all_src[0].get("source_type")
    assert st
    filtered = client.get(f"/api/sources?source_type={st}&limit=500").json()
    assert filtered
    assert all(str(s.get("source_type") or "").upper() == str(st).upper() for s in filtered)
    multi = client.get("/api/sources?source_type=PATENT,NEWS&limit=500").json()
    assert all(str(s.get("source_type") or "").upper() in {"PATENT", "NEWS"} for s in multi)


def test_sources_query_filter(client):
    all_src = client.get("/api/sources?limit=50").json()
    assert all_src
    publisher = all_src[0].get("publisher") or ""
    assert publisher
    hit = client.get(f"/api/sources?q={publisher[: min(6, len(publisher))]}&limit=50").json()
    assert any(s.get("publisher") == publisher for s in hit)
    miss = client.get("/api/sources?q=___no_match_src_xyz___&limit=50").json()
    assert miss == []


def test_observations_type_filter(client):
    all_obs = client.get("/api/observations?limit=100").json()
    assert all_obs
    ot = all_obs[0].get("observation_type")
    assert ot
    filtered = client.get(f"/api/observations?observation_type={ot}&limit=100").json()
    assert filtered
    assert all(o.get("observation_type") == ot for o in filtered)


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

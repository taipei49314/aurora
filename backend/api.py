"""AURORA HTTP API (spec §26).

FastAPI layer over the discovery engine. State is held in an in-memory
repository seeded from the Northstar corpus at startup; runs are immutable once
created. Side-effecting operations use POST; errors use the structured error
model with proper status codes (never a bare 500).

Run:  uvicorn api:app --app-dir backend --reload
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "datasets" / "northstar"))

from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from aurora import import_package, Taxonomy, run_pipeline, DEFAULT_CONFIG
from aurora.models import to_dict
from aurora.errors import AuroraError
from aurora.backtest import run_backtest
from aurora import divergence
import generate

app = FastAPI(title="AURORA", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

TAXONOMY_PATH = ROOT / "datasets" / "taxonomy" / "taxonomy.json"


class _Repo:
    def __init__(self):
        pkg, _gt = generate.generate()
        self.snapshot = import_package(pkg)
        self.taxonomy = Taxonomy.load(TAXONOMY_PATH)
        self.runs: dict[str, object] = {}
        self.backtests: dict[str, dict] = {}
        # seed one full run
        self.create_run(None)

    def create_run(self, cutoff):
        run = run_pipeline(self.snapshot, self.taxonomy, DEFAULT_CONFIG, cutoff_date=cutoff)
        self.runs[run.run_id] = run
        return run

    def hyp(self, run_id, hyp_id):
        run = self.runs.get(run_id)
        if not run:
            for r in self.runs.values():
                for h in r.hypotheses:
                    if h.hypothesis_id == hyp_id:
                        return h
            return None
        for h in run.hypotheses:
            if h.hypothesis_id == hyp_id:
                return h
        return None

    def find_hyp(self, hyp_id):
        for r in self.runs.values():
            for h in r.hypotheses:
                if h.hypothesis_id == hyp_id:
                    return h
        return None


REPO = _Repo()


@app.exception_handler(AuroraError)
async def aurora_error_handler(_request, exc: AuroraError):
    from fastapi.responses import JSONResponse
    status = 422 if exc.error_code in {"INVALID_CUTOFF_DATE", "SCHEMA_VALIDATION_FAILED"} else 400
    return JSONResponse(status_code=status, content=exc.to_dict())


@app.get("/api/health")
def health():
    return {"status": "ok", "engine": DEFAULT_CONFIG.engine_version,
            "snapshot": REPO.snapshot.snapshot_id, "runs": len(REPO.runs)}


@app.get("/api/stats")
def stats():
    """Snapshot corpus stats for dashboards (external_ids coverage, tier mix)."""
    s = REPO.snapshot
    tier_counts: dict = {}
    source_type_counts: dict = {}
    with_family = 0
    with_event = 0
    with_event_id = 0
    with_outlet = 0
    with_wire = 0
    with_geo = 0
    with_license = 0
    license_counts: dict = {}
    for src in s.sources:
        t = (src.reliability_tier or "C").upper()
        tier_counts[t] = tier_counts.get(t, 0) + 1
        st = src.source_type or "?"
        source_type_counts[st] = source_type_counts.get(st, 0) + 1
        if getattr(src, "family_id", None) or (src.metadata or {}).get("family_id"):
            with_family += 1
        if getattr(src, "event_date", None) or (src.metadata or {}).get("event_date"):
            with_event += 1
        if getattr(src, "event_id", None) or (src.metadata or {}).get("event_id"):
            with_event_id += 1
        if getattr(src, "outlet_domain", None) or (src.metadata or {}).get("outlet_domain"):
            with_outlet += 1
        if getattr(src, "wire_id", None) or (src.metadata or {}).get("wire_id"):
            with_wire += 1
        if getattr(src, "geo", None) or (src.metadata or {}).get("geo"):
            with_geo += 1
        lic = (getattr(src, "license", None) or (src.metadata or {}).get("license") or "").strip()
        if lic:
            with_license += 1
            license_counts[lic] = license_counts.get(lic, 0) + 1
    type_counts: dict = {}
    obs_with_event_id = 0
    obs_with_geo = 0
    obs_with_document_id = 0
    obs_with_char_span = 0
    unique_event_ids: set = set()
    country_counts: dict = {}
    for o in s.observations:
        type_counts[o.observation_type] = type_counts.get(o.observation_type, 0) + 1
        eid = getattr(o, "event_id", None) or (o.metadata or {}).get("event_id")
        if eid:
            obs_with_event_id += 1
            unique_event_ids.add(str(eid))
        g = getattr(o, "geo", None) or (o.metadata or {}).get("geo") or {}
        if g:
            obs_with_geo += 1
            c = (g.get("country") if isinstance(g, dict) else None) or ""
            if c:
                country_counts[c] = country_counts.get(c, 0) + 1
        if getattr(o, "document_id", None) or (o.metadata or {}).get("document_id"):
            obs_with_document_id += 1
        if getattr(o, "char_span", None) or (o.metadata or {}).get("char_span"):
            obs_with_char_span += 1
    with_ext = sum(1 for e in s.entities if e.external_ids)
    entities_with_country = sum(1 for e in s.entities if (e.country or "").strip())
    entity_country_counts: dict = {}
    for e in s.entities:
        c = (e.country or "").strip()
        if c:
            entity_country_counts[c] = entity_country_counts.get(c, 0) + 1
    ext_systems: dict = {}
    for e in s.entities:
        for x in e.external_ids or []:
            sys = (x.get("system") if isinstance(x, dict) else None) or "?"
            ext_systems[sys] = ext_systems.get(sys, 0) + 1
    return {
        "snapshot_id": s.snapshot_id,
        "counts": dict(s.counts or {}),
        "entities_with_external_ids": with_ext,
        "entities_total": len(s.entities),
        "entities_with_country": entities_with_country,
        "entity_country_counts": entity_country_counts,
        "sources_total": len(s.sources),
        "sources_with_family_id": with_family,
        "sources_with_event_date": with_event,
        "sources_with_event_id": with_event_id,
        "sources_with_outlet_domain": with_outlet,
        "sources_with_wire_id": with_wire,
        "sources_with_geo": with_geo,
        "sources_with_license": with_license,
        "license_counts": license_counts,
        "observations_with_event_id": obs_with_event_id,
        "observations_with_geo": obs_with_geo,
        "observations_with_document_id": obs_with_document_id,
        "observations_with_char_span": obs_with_char_span,
        "documents_total": len(getattr(s, "documents", None) or []),
        "observation_country_counts": country_counts,
        "unique_event_ids": len(unique_event_ids),
        "reliability_tier_counts": tier_counts,
        "source_type_counts": source_type_counts,
        "observation_type_counts": type_counts,
        "external_id_systems": ext_systems,
        "engine": DEFAULT_CONFIG.engine_version,
    }


class ResolveBody(BaseModel):
    ref: str
    external_ids: Optional[list] = None


@app.post("/api/resolve")
def resolve_entity(body: ResolveBody):
    """Dry-run entity resolution against the current snapshot (name / ext ids)."""
    from aurora.entity_resolution import EntityResolver, parse_entity_ref

    resolver = EntityResolver(REPO.snapshot.entities)
    name, ext = parse_entity_ref(body.ref)
    extra = list(body.external_ids or [])
    eid = resolver.resolve(name, external_ids=list(ext) + extra)
    if eid is None:
        raise HTTPException(404, f"cannot resolve {body.ref!r}")
    ent = next(e for e in REPO.snapshot.entities if e.entity_id == eid)
    return {
        "ref": body.ref,
        "entity_id": eid,
        "canonical_name": ent.canonical_name,
        "aliases": list(ent.aliases or []),
        "external_ids": list(ent.external_ids or []),
    }


@app.get("/api/entities")
def entities(limit: int = 200, q: Optional[str] = None):
    """List entities; optional ``q`` filters name/aliases/external_ids/id."""
    rows = [to_dict(e) for e in REPO.snapshot.entities]
    if q:
        needle = q.strip().lower()
        filtered = []
        for r in rows:
            blob = json.dumps(r, ensure_ascii=False).lower()
            if needle in blob:
                filtered.append(r)
        rows = filtered
    return rows[:limit]


@app.get("/api/entities/{entity_id}")
def entity(entity_id: str):
    for e in REPO.snapshot.entities:
        if e.entity_id == entity_id:
            return to_dict(e)
    raise HTTPException(404, "entity not found")


@app.get("/api/documents")
def documents(limit: int = 200, q: Optional[str] = None):
    """List optional full-document records (engine 0.1.15+)."""
    rows = [to_dict(d) for d in (getattr(REPO.snapshot, "documents", None) or [])]
    if q:
        needle = q.strip().lower()
        rows = [r for r in rows if needle in json.dumps(r, ensure_ascii=False).lower()]
    return rows[:limit]


@app.get("/api/documents/{document_id}")
def document(document_id: str):
    for d in getattr(REPO.snapshot, "documents", None) or []:
        if d.document_id == document_id:
            return to_dict(d)
    raise HTTPException(404, "document not found")


@app.get("/api/sources")
def sources(
    limit: int = 200,
    reliability_tier: Optional[str] = None,
    source_type: Optional[str] = None,
    q: Optional[str] = None,
):
    """List sources. Optional filters:

    - ``reliability_tier``: single letter or comma list (``A``, ``B,C``)
    - ``source_type``: e.g. ``PATENT``, ``NEWS`` (comma list ok)
    - ``q``: case-insensitive substring over the serialized row
    """
    rows = [to_dict(s) for s in REPO.snapshot.sources]
    if reliability_tier:
        tiers = {t.strip().upper() for t in reliability_tier.split(",") if t.strip()}
        allowed = {"A", "B", "C", "D"}
        bad = tiers - allowed
        if bad:
            raise HTTPException(
                422,
                f"reliability_tier must be A/B/C/D (got {sorted(bad)})",
            )
        rows = [
            r for r in rows
            if str(r.get("reliability_tier") or "C").upper() in tiers
        ]
    if source_type:
        types = {t.strip().upper() for t in source_type.split(",") if t.strip()}
        rows = [
            r for r in rows
            if str(r.get("source_type") or "").upper() in types
        ]
    if q:
        needle = q.strip().lower()
        if needle:
            rows = [
                r for r in rows
                if needle in json.dumps(r, ensure_ascii=False).lower()
            ]
    return rows[:limit]


@app.get("/api/observations")
def observations(
    limit: int = 500,
    observation_type: Optional[str] = None,
    q: Optional[str] = None,
):
    """List observations. Optional ``observation_type`` (comma list) and ``q``."""
    rows = [to_dict(o) for o in REPO.snapshot.observations]
    if observation_type:
        types = {t.strip() for t in observation_type.split(",") if t.strip()}
        rows = [r for r in rows if str(r.get("observation_type") or "") in types]
    if q:
        needle = q.strip().lower()
        if needle:
            rows = [
                r for r in rows
                if needle in json.dumps(r, ensure_ascii=False).lower()
            ]
    return rows[:limit]


@app.get("/api/snapshots")
def snapshots():
    s = REPO.snapshot
    return [{"snapshot_id": s.snapshot_id, "created_at": s.created_at, "counts": s.counts}]


@app.post("/api/imports")
async def import_upload(file: UploadFile = File(...)):
    """Upload a JSON package {entities, sources, observations}; it becomes the
    current snapshot. Existing runs are immutable and keep their old snapshot."""
    try:
        raw = json.loads((await file.read()).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, "file must be UTF-8 JSON")
    if not isinstance(raw, dict):
        raise HTTPException(400, "package must be a JSON object with entities/sources/observations")
    snap = import_package(raw)
    REPO.snapshot = snap
    return {"snapshot_id": snap.snapshot_id, "counts": snap.counts,
            "import_errors": len(snap.import_errors)}


@app.get("/api/exports")
def export_package():
    """Package in the raw import format — feed it back to /api/imports.

    Internal objects store resolved ids; the import format wants source refs and
    entity *names*, so this maps back: excerpt is lifted out of metadata so the
    source content hash (and thus every derived id) recomputes identically."""
    s = REPO.snapshot
    name_by_id = {e.entity_id: e.canonical_name for e in s.entities}
    entities = []
    for e in s.entities:
        entities.append({
            "entity_type": e.entity_type,
            "canonical_name": e.canonical_name,
            "aliases": list(e.aliases or []),
            "description": e.description,
            "country": e.country,
            "external_ids": list(e.external_ids or []),
            "metadata": dict(e.metadata or {}),
        })
    sources = []
    for src in s.sources:
        meta = dict(src.metadata)
        excerpt = meta.pop("excerpt", "")
        family_id = getattr(src, "family_id", "") or meta.pop("family_id", "") or ""
        if family_id:
            meta.pop("family_id", None)
        event_date = getattr(src, "event_date", None) or meta.pop("event_date", None) or None
        if event_date:
            meta.pop("event_date", None)
        event_id = getattr(src, "event_id", "") or meta.pop("event_id", "") or ""
        if event_id:
            meta.pop("event_id", None)
        outlet_domain = getattr(src, "outlet_domain", "") or meta.pop("outlet_domain", "") or ""
        if outlet_domain:
            meta.pop("outlet_domain", None)
            meta.pop("domain", None)
        wire_id = getattr(src, "wire_id", "") or meta.pop("wire_id", "") or ""
        if wire_id:
            meta.pop("wire_id", None)
        geo = dict(getattr(src, "geo", None) or meta.pop("geo", None) or {})
        if geo:
            meta.pop("geo", None)
            meta.pop("location", None)
        license_s = getattr(src, "license", "") or meta.pop("license", "") or ""
        if license_s:
            meta.pop("license", None)
        sources.append({
            "ref": src.source_id, "source_type": src.source_type,
            "publisher": src.publisher, "title": src.title,
            "published_at": src.published_at,
            "event_date": event_date,
            "event_id": event_id,
            "outlet_domain": outlet_domain,
            "wire_id": wire_id,
            "geo": geo,
            "license": license_s,
            "url_or_local_path": src.url_or_local_path,
            "independence_group": src.independence_group,
            "reliability_tier": src.reliability_tier,
            "language": src.language,
            "family_id": family_id,
            "excerpt": excerpt, "metadata": meta,
        })
    observations = []
    for o in s.observations:
        meta = {k: v for k, v in o.metadata.items()
                if k not in ("source_type", "independence_group")}
        event_id = getattr(o, "event_id", "") or meta.pop("event_id", "") or ""
        if event_id:
            meta.pop("event_id", None)
        geo = dict(getattr(o, "geo", None) or meta.pop("geo", None) or {})
        if geo:
            meta.pop("geo", None)
            meta.pop("location", None)
        document_id = getattr(o, "document_id", "") or meta.pop("document_id", "") or ""
        if document_id:
            meta.pop("document_id", None)
        char_span = getattr(o, "char_span", None)
        if char_span is None:
            char_span = meta.pop("char_span", None)
        else:
            meta.pop("char_span", None)
        observations.append({
            "source_ref": o.source_id, "observation_type": o.observation_type,
            "subject": name_by_id.get(o.subject_entity, o.subject_entity),
            "object": name_by_id.get(o.object_entity, "") if o.object_entity else "",
            "observed_at": o.observed_at, "numeric_value": o.numeric_value,
            "unit": o.unit, "text_excerpt": o.text_excerpt,
            "confidence": o.confidence, "event_id": event_id, "geo": geo,
            "document_id": document_id,
            "char_span": char_span,
            "metadata": meta,
        })
    documents = []
    for d in getattr(s, "documents", None) or []:
        documents.append({
            "document_id": d.document_id,
            "source_ref": d.source_id,
            "title": d.title,
            "text": d.text,
            "url_or_local_path": d.url_or_local_path,
            "language": d.language,
            "license": d.license,
            "metadata": dict(d.metadata or {}),
        })
    out = {"entities": entities, "sources": sources, "observations": observations}
    if documents:
        out["documents"] = documents
    return out


@app.post("/api/snapshots")
def persist_snapshot():
    """Persist the current snapshot to the SQLite store (backend/aurora.db).
    Content-addressed and idempotent: re-posting the same snapshot is a no-op."""
    from aurora import store_sql
    engine = store_sql.make_engine(f"sqlite:///{ROOT / 'backend' / 'aurora.db'}")
    store_sql.save_snapshot(engine, REPO.snapshot)
    return {"snapshot_id": REPO.snapshot.snapshot_id,
            "persisted_to": "backend/aurora.db"}


class RunRequest(BaseModel):
    cutoff_date: Optional[str] = None  # Optional (not X|Y): must eval on Python 3.9


@app.post("/api/research-runs")
def create_run(req: RunRequest):
    run = REPO.create_run(req.cutoff_date)
    return {"run_id": run.run_id, "status": run.status, "cutoff_date": run.cutoff_date}


@app.get("/api/research-runs")
def list_runs():
    return [{"run_id": r.run_id, "cutoff_date": r.cutoff_date, "status": r.status,
             "created_at": r.created_at, "n_hypotheses": len(r.hypotheses)} for r in REPO.runs.values()]


@app.get("/api/research-runs/{run_id}")
def get_run(run_id: str):
    r = REPO.runs.get(run_id)
    if not r:
        raise HTTPException(404, "run not found")
    return r.to_dict()


@app.get("/api/research-runs/{run_id}/status")
def run_status(run_id: str):
    r = REPO.runs.get(run_id)
    if not r:
        raise HTTPException(404, "run not found")
    return {"run_id": r.run_id, "status": r.status, "stage_timings": r.stage_timings}


@app.get("/api/research-runs/{run_id}/hypotheses")
def run_hypotheses(run_id: str):
    r = REPO.runs.get(run_id)
    if not r:
        raise HTTPException(404, "run not found")
    return [to_dict(h) for h in r.hypotheses]


@app.get("/api/hypotheses/{hyp_id}")
def get_hyp(hyp_id: str):
    h = REPO.find_hyp(hyp_id)
    if not h:
        raise HTTPException(404, "hypothesis not found")
    return to_dict(h)


class HumanName(BaseModel):
    human_name: str


@app.patch("/api/hypotheses/{hyp_id}/human-name")
def set_human_name(hyp_id: str, body: HumanName):
    h = REPO.find_hyp(hyp_id)
    if not h:
        raise HTTPException(404, "hypothesis not found")
    # human name is a label only; it does not alter evidence or scores (spec §13)
    h.human_name = body.human_name
    return {"hypothesis_id": hyp_id, "human_name": h.human_name}


@app.get("/api/hypotheses/{hyp_id}/evidence")
def hyp_evidence(hyp_id: str):
    h = REPO.find_hyp(hyp_id)
    if not h:
        raise HTTPException(404, "hypothesis not found")
    return {"supporting": h.strongest_supporting_evidence, "observation_ids": h.observation_ids}


@app.get("/api/hypotheses/{hyp_id}/counterevidence")
def hyp_counter(hyp_id: str):
    h = REPO.find_hyp(hyp_id)
    if not h:
        raise HTTPException(404, "hypothesis not found")
    return {"counterevidence": h.strongest_counterevidence, "missing_evidence": h.missing_evidence,
            "disconfirmation_conditions": h.disconfirmation_conditions,
            "contradiction_score": h.contradiction_score}


@app.get("/api/hypotheses/{hyp_id}/value-chain")
def hyp_value_chain(hyp_id: str):
    h = REPO.find_hyp(hyp_id)
    if not h:
        raise HTTPException(404, "hypothesis not found")
    return h.score_explanation.get("value_chain", {})


@app.get("/api/hypotheses/{hyp_id}/bottlenecks")
def hyp_bottlenecks(hyp_id: str):
    h = REPO.find_hyp(hyp_id)
    if not h:
        raise HTTPException(404, "hypothesis not found")
    return h.score_explanation.get("bottlenecks", [])


@app.get("/api/hypotheses/{hyp_id}/graph")
def hyp_graph(hyp_id: str):
    """Nodes (value-chain roles) + edges + bottleneck flags for the Discovery Map."""
    h = REPO.find_hyp(hyp_id)
    if not h:
        raise HTTPException(404, "hypothesis not found")
    vc = h.score_explanation.get("value_chain", {})
    bn_ids = {b["entity_id"]: b["bottleneck_score"] for b in h.score_explanation.get("bottlenecks", [])}
    name_by_id = {e.entity_id: e.canonical_name for e in REPO.snapshot.entities}
    nodes = [{"id": n["entity_id"], "name": name_by_id.get(n["entity_id"], n["entity_id"]),
              "role": n["role"], "bottleneck_score": bn_ids.get(n["entity_id"], 0.0)}
             for n in vc.get("nodes", [])]
    return {"nodes": nodes, "edges": vc.get("edges", [])}


@app.get("/api/hypotheses/{hyp_id}/timeline")
def hyp_timeline(hyp_id: str):
    """Observation activity over time, grouped by year and observation type."""
    h = REPO.find_hyp(hyp_id)
    if not h:
        raise HTTPException(404, "hypothesis not found")
    ents = set(h.entity_ids)
    buckets: dict[str, dict[str, int]] = {}
    for o in REPO.snapshot.observations:
        if o.subject_entity in ents and o.observed_at:
            year = o.observed_at[:4]
            buckets.setdefault(year, {}).setdefault(o.observation_type, 0)
            buckets[year][o.observation_type] += 1
    return {"timeline": [{"year": y, "by_type": buckets[y],
                          "total": sum(buckets[y].values())} for y in sorted(buckets)]}


class BacktestRequest(BaseModel):
    cutoffs: list[str]


@app.post("/api/backtests")
def create_backtest(req: BacktestRequest):
    bt = run_backtest(REPO.snapshot, REPO.taxonomy, req.cutoffs, DEFAULT_CONFIG)
    bt_id = f"bt_{abs(hash(tuple(req.cutoffs)))}"
    REPO.backtests[bt_id] = bt
    return {"backtest_id": bt_id, **bt}  # includes tracks so the UI can render them


@app.get("/api/backtests/{bt_id}")
def get_backtest(bt_id: str):
    bt = REPO.backtests.get(bt_id)
    if not bt:
        raise HTTPException(404, "backtest not found")
    return bt


@app.get("/api/research-runs/{run_id}/compare/{other_id}")
def compare_runs(run_id: str, other_id: str):
    a, b = REPO.runs.get(run_id), REPO.runs.get(other_id)
    if not a or not b:
        raise HTTPException(404, "run not found")
    return divergence.compare(a, b)


@app.get("/api/research-runs/{run_id}/divergence/{other_id}")
def divergence_runs(run_id: str, other_id: str):
    a, b = REPO.runs.get(run_id), REPO.runs.get(other_id)
    if not a or not b:
        raise HTTPException(404, "run not found")
    return divergence.first_divergence(a, b)

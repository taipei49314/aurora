"""Discovery pipeline orchestration (spec §10, §22).

Runs every stage in order and produces an immutable ResearchRun of scored,
classified hypotheses with full provenance. Each stage is a separate module with
its own inputs/outputs — there is deliberately no monolithic
``discover_industries()`` (spec §10 forbids it).
"""
from __future__ import annotations

import time
from collections import Counter
from datetime import datetime, timezone

from .config import EngineConfig, DEFAULT_CONFIG
from .ids import content_hash, prefixed_id
from .models import Hypothesis, REAL_INVESTMENT_TYPES, DEMAND_TYPES
from .store import ResearchRun, Snapshot
from . import leakage, clustering, graph as graphmod, scoring, classify
from .taxonomy import Taxonomy
from .naming_gap import naming_gap
from .hype import hype_assessment
from .counterevidence import analyze as counter_analyze
from .value_chain import build as build_value_chain
from .bottleneck import analyze as bottleneck_analyze
from .signals import entity_signal_summary
from .features import cosine


def _generated_name(cluster, vectors, entities) -> str:
    agg: dict[str, float] = {}
    for e in cluster:
        for t, v in vectors.get(e, {}).items():
            if t.startswith("obs::") or "_" not in t and len(t) < 4:
                continue
            agg[t] = agg.get(t, 0.0) + v
    top = sorted(agg.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    label = "-".join(t.replace("_", " ") for t, _ in top) or "unnamed-cluster"
    return f"{label} (auto)"


def _data_quality_penalty(cluster_obs) -> float:
    if not cluster_obs:
        return 0.0
    missing = sum(1 for o in cluster_obs if not o.observed_at)
    lowconf = sum(1 for o in cluster_obs if (o.confidence or 0) < 0.4)
    frac = (missing + lowconf) / (2 * len(cluster_obs))
    return round(25.0 * frac, 2)


def run_pipeline(snapshot: Snapshot, taxonomy: Taxonomy, cfg: EngineConfig = DEFAULT_CONFIG,
                 cutoff_date: str | None = None) -> ResearchRun:
    t0 = time.perf_counter()
    timings: dict[str, float] = {}

    def mark(stage):
        nonlocal t0
        now = time.perf_counter()
        timings[stage] = round(now - t0, 4)
        t0 = now

    # --- cutoff / leakage ---
    cut = leakage.apply_cutoff(snapshot.observations, snapshot.sources, cutoff_date)
    observations = cut["observations"]
    leakage.assert_no_leakage(observations, cutoff_date)
    entities = snapshot.entities
    resolved_group = snapshot.resolved_group
    mark("cutoff")

    # --- features + clustering ---
    vectors = clustering.entity_vectors(entities, observations)
    fs_clusters = clustering.feature_space_clusters(entities, observations, cfg.clustering, vectors)
    graph_comm = clustering.graph_clusters(entities, observations, cfg.clustering)
    agreement = clustering.pairwise_agreement(fs_clusters, graph_comm)
    stability = clustering.stability_scores(entities, observations, cfg.clustering)
    adj = graphmod.build_graph(entities, observations, cfg.clustering.edge_min_weight)
    mark("clustering")

    obs_by_subject: dict[str, list] = {}
    for o in observations:
        obs_by_subject.setdefault(o.subject_entity, []).append(o)
    sig = entity_signal_summary(observations, resolved_group)

    hypotheses = []
    run_stub = "pending"
    for cluster in fs_clusters:
        cluster_obs = [o for eid in cluster for o in obs_by_subject.get(eid, [])]
        if not cluster_obs:
            continue
        hid = prefixed_id("hyp", cutoff_date or "full", *sorted(cluster))

        # taxonomy comparison
        cvec = taxonomy.cluster_vector(cluster, entities, observations)
        match = taxonomy.best_match(cvec)

        ng = naming_gap(cluster, entities, observations, vectors, match["similarity"])
        hy = hype_assessment(cluster, observations)
        ce = counter_analyze(cluster, observations, resolved_group)
        vc = build_value_chain(hid, cluster, entities, observations)
        bn = bottleneck_analyze(hid, cluster, entities, observations, fs_clusters, adj)

        # cluster-level ratios
        types = Counter(o.observation_type for o in cluster_obs)
        n = len(cluster_obs)
        real_ratio = sum(types[t] for t in REAL_INVESTMENT_TYPES) / n
        demand_ratio = sum(types[t] for t in DEMAND_TYPES) / n
        accel = sum(sig.get(e, {}).get("acceleration", 0.0) for e in cluster) / max(1, len(cluster))
        src_ids = [o.source_id for o in cluster_obs]
        indep_groups = {resolved_group.get(s, s) for s in src_ids}
        distinct_source_types = len({o.metadata.get("source_type") for o in cluster_obs})
        stab = clustering.cluster_stability(cluster, stability)

        components = {
            "novelty_score": round(100.0 * ng["taxonomy_distance"], 2),
            "coherence_score": round(100.0 * ng["capability_coherence"], 2),
            "acceleration_score": round(100.0 * (accel + 1) / 2, 2),
            "value_chain_score": vc["value_chain_score"],
            "real_investment_score": scoring.saturating(real_ratio, 0.35),
            "demand_score": scoring.saturating(demand_ratio, 0.18),
            "bottleneck_score": bn["bottleneck_score"],
            "naming_gap_score": ng["naming_gap_score"],
            "source_independence_score": scoring.saturating(len(indep_groups), 5),
            "cluster_stability_score": round(100.0 * stab, 2),
            "hype_risk_score": hy["hype_risk_score"],
            "contradiction_score": ce["contradiction_score"],
            "data_quality_penalty": _data_quality_penalty(cluster_obs),
        }
        scored = scoring.assemble(components, cfg.scoring)

        status, reasons = classify.classify(
            independent_sources=len(indep_groups), distinct_source_types=distinct_source_types,
            n_entities=len(cluster), taxonomy_similarity=match["similarity"],
            straddles_two=match["straddles_two"], hype_risk=hy["hype_risk_score"],
            contradiction=ce["contradiction_score"], cluster_stability=stab,
            overall=scored["overall_score"], value_chain=vc["value_chain_score"],
            real_investment=components["real_investment_score"], demand=components["demand_score"],
            cfg=cfg.classification,
        )

        first_dates = sorted(o.observed_at for o in cluster_obs if o.observed_at)
        h = Hypothesis(
            hypothesis_id=hid, generated_name=_generated_name(cluster, vectors, entities),
            human_name=None, status=status,
            summary="; ".join(reasons), created_from_run=run_stub,
            first_detected_at=(first_dates[0] if first_dates else None),
            novelty_score=components["novelty_score"], coherence_score=components["coherence_score"],
            acceleration_score=components["acceleration_score"], value_chain_score=components["value_chain_score"],
            real_investment_score=components["real_investment_score"], demand_score=components["demand_score"],
            bottleneck_score=components["bottleneck_score"], hype_risk_score=components["hype_risk_score"],
            contradiction_score=components["contradiction_score"], naming_gap_score=components["naming_gap_score"],
            source_independence_score=components["source_independence_score"],
            cluster_stability_score=components["cluster_stability_score"],
            data_quality_penalty=components["data_quality_penalty"], overall_score=scored["overall_score"],
            confidence_band=scored["confidence_band"], entity_ids=sorted(cluster),
            observation_ids=sorted(o.observation_id for o in cluster_obs),
            score_explanation={"scoring": scored, "naming_gap": ng, "hype": hy, "match": match,
                               "value_chain_roles": vc["roles_present"]},
            strongest_supporting_evidence=ce["strongest_supporting_evidence"],
            strongest_counterevidence=ce["strongest_counterevidence"],
            missing_evidence=ce["missing_evidence"],
            disconfirmation_conditions=ce["disconfirmation_conditions"],
            existing_industry_similarity=match,
            cluster_method="feature_space",
        )
        # attach structured extras for the API/UI
        h.score_explanation["value_chain"] = {"nodes": [n.__dict__ for n in vc["nodes"]], "edges": vc["edges"]}
        h.score_explanation["bottlenecks"] = [c.__dict__ for c in bn["candidates"][:5]]
        hypotheses.append(h)
    mark("hypotheses")

    hypotheses.sort(key=lambda h: (-h.overall_score, h.hypothesis_id))
    result_hash = content_hash([
        [h.hypothesis_id, h.status, h.overall_score, h.entity_ids] for h in hypotheses
    ])
    run_id = f"run_{content_hash(snapshot.snapshot_id, cutoff_date or 'full', cfg.manifest(), result_hash)}"
    for h in hypotheses:
        h.created_from_run = run_id

    run = ResearchRun(
        run_id=run_id, snapshot_id=snapshot.snapshot_id, cutoff_date=cutoff_date,
        engine_version=cfg.engine_version, feature_version=cfg.feature_version,
        taxonomy_version=cfg.taxonomy_version, algorithm_config=cfg.manifest()["clustering"],
        scoring_config=cfg.manifest()["scoring"], created_at=datetime.now(timezone.utc).isoformat(),
        status="COMPLETE", input_manifest_hash=snapshot.input_manifest_hash(),
        result_manifest_hash=result_hash, hypotheses=hypotheses,
        leakage_manifest={**cut["manifest"], "cluster_agreement": round(agreement, 4)},
        stage_timings=timings,
    )
    return run

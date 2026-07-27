"""AURORA as a Frontier Atlas fleet module.

Offline throughout: no mothership is contacted. What is tested here is the part
that can lie — how a research run is turned into findings and predictions.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from aurora import atlas


def hypothesis(**kw):
    base = dict(
        hypothesis_id="hyp_test", generated_name="test-cluster", status="INDUSTRY_CANDIDATE",
        summary="meets candidate thresholds", overall_score=72.3, confidence_band="MEDIUM",
        entity_ids=["ent_a", "ent_b", "ent_c"], existing_industry_similarity={"similarity": 0.0},
        missing_evidence=[])
    base.update(kw)
    return SimpleNamespace(**base)


def research_run(hypotheses, *, cutoff=None, manifest=None):
    return SimpleNamespace(
        run_id="run_test", snapshot_id="snap_test", cutoff_date=cutoff,
        engine_version="0.1.46", feature_version="1", taxonomy_version="1",
        created_at="2026-07-27T04:00:00+00:00", result_manifest_hash="deadbeef",
        hypotheses=hypotheses,
        leakage_manifest=manifest if manifest is not None else {
            "cutoff_date": cutoff, "included_observation_count": 3119,
            "excluded_future_observation_count": 0,
            "excluded_undated_observation_count": 0})


# --------------------------------------------------------------- findings

@pytest.mark.unit
def test_findings_state_the_run_not_a_conclusion():
    found = atlas.findings_from(research_run([hypothesis()]))
    joined = "\n".join(found)
    assert "被分類為 INDUSTRY_CANDIDATE" in joined
    assert "總分 72.3" in joined
    # The module reports classification, never a claim about the world.
    for banned in ("正在成形", "將會成為", "值得投資", "建議"):
        assert banned not in joined


@pytest.mark.unit
def test_engine_reasons_are_forwarded_not_paraphrased():
    found = atlas.findings_from(research_run(
        [hypothesis(summary="counterevidence dominates (contradiction=100)")]))
    assert any("分類理由是:counterevidence dominates (contradiction=100)" in f
               for f in found)


@pytest.mark.unit
def test_existing_variant_reports_its_similarity():
    found = atlas.findings_from(research_run([hypothesis(
        status="EXISTING_INDUSTRY_VARIANT", existing_industry_similarity={"similarity": 0.57})]))
    assert any("最高相似度為 0.57" in f for f in found)


@pytest.mark.unit
def test_similarity_finding_only_for_existing_variants():
    found = atlas.findings_from(research_run([hypothesis(
        status="INDUSTRY_CANDIDATE", existing_industry_similarity={"similarity": 0.57})]))
    assert not any("最高相似度" in f for f in found)


@pytest.mark.unit
def test_missing_evidence_is_reported_when_present():
    found = atlas.findings_from(research_run(
        [hypothesis(missing_evidence=["PATENT_ACTIVITY", "CAPEX_ACTIVITY"])]))
    assert any("完全沒有這幾類證據:PATENT_ACTIVITY, CAPEX_ACTIVITY" in f for f in found)


@pytest.mark.unit
def test_leakage_accounting_only_appears_for_a_historical_run():
    full = atlas.findings_from(research_run([hypothesis()]))
    assert not any("為守住 cutoff" in f for f in full)

    historical = atlas.findings_from(research_run([hypothesis()], cutoff="2021-12-31",
        manifest={"cutoff_date": "2021-12-31", "included_observation_count": 900,
                  "excluded_future_observation_count": 2219,
                  "excluded_undated_observation_count": 0}))
    assert any("排除了 2219 筆晚於切點的觀察" in f for f in historical)


@pytest.mark.unit
def test_every_finding_is_one_self_contained_line():
    found = atlas.findings_from(research_run(
        [hypothesis(generated_name="a\nb", summary="line one\nline two")]))
    for finding in found:
        assert "\n" not in finding
        assert finding.strip()


@pytest.mark.unit
def test_findings_survive_a_snapshot_without_counts():
    found = atlas.findings_from(research_run([hypothesis()]), snapshot=None)
    assert found and "分出 1 個群集" in found[0]


# ------------------------------------------------------------- null model

@pytest.mark.unit
def test_no_cutoffs_means_no_baseline():
    assert atlas.retention_null_model(None, None, []) is None


@pytest.mark.unit
def test_prediction_is_refused_without_a_baseline(monkeypatch):
    """No measured baseline -> findings only, and the reason is recorded.

    A prediction whose null model was invented is worse than no prediction: it
    turns the ledger into decoration. This is the fail-closed path.
    """
    calls = {"predictions": 0}

    class FakeClient:
        def __init__(self, base_url):
            pass

        def ensure_workspace(self, name, description=""):
            return "ws_1"

        def submit_run(self, ws, report):
            return {"module_run_id": "mr_1", "source_id": "src_1",
                    "report_hash": "h", "findings": report.findings}

        def cite_finding(self, run_id, index, text, **kw):
            return {"claim_id": f"claim_{index}", "evidence_id": f"ev_{index}"}

        def register_prediction(self, *a, **kw):
            calls["predictions"] += 1
            return {"id": "pred_1"}

    monkeypatch.setattr(atlas, "AtlasClient", FakeClient)
    pushed = atlas.push_run(research_run([hypothesis()]), base_url="http://x",
                            null_model=None)
    assert calls["predictions"] == 0
    assert pushed["predictions"] == []
    assert "沒有經驗基準率" in pushed["predictions_skipped_reason"]
    assert pushed["findings"] > 0, "findings still land; they are observations"


@pytest.mark.unit
def test_prediction_is_registered_once_a_baseline_exists(monkeypatch):
    registered = []

    class FakeClient:
        def __init__(self, base_url):
            pass

        def ensure_workspace(self, name, description=""):
            return "ws_1"

        def submit_run(self, ws, report):
            return {"module_run_id": "mr_1", "source_id": "src_1", "report_hash": "h"}

        def cite_finding(self, run_id, index, text, **kw):
            return {"claim_id": f"claim_{index}", "evidence_id": f"ev_{index}"}

        def register_prediction(self, run_id, claim_id, **kw):
            registered.append(kw)
            return {"id": f"pred_{len(registered)}"}

    monkeypatch.setattr(atlas, "AtlasClient", FakeClient)
    baseline = {"usable": True, "statement": "經驗保留率基準:...保留率 60%。",
                "retention_rate": 0.6, "ever_candidate": 12}
    pushed = atlas.push_run(
        research_run([hypothesis(), hypothesis(status="HYPE_CLUSTER",
                                              generated_name="loud-cluster")]),
        base_url="http://x", null_model=baseline, horizon_days=180)

    assert len(pushed["predictions"]) == 1, "only candidates get a prediction"
    rule = registered[0]["resolution_rule"]
    assert f"Jaccard >= {atlas.CLUSTER_MATCH_JACCARD}" in rule
    assert "engine=0.1.46" in rule, "the rule must pin the engine config to be re-runnable"
    assert "correct" in rule and "incorrect" in rule and "ambiguous" in rule
    assert registered[0]["null_model"] == baseline["statement"]
    assert registered[0]["horizon_days"] == 180


@pytest.mark.unit
def test_report_carries_the_runs_own_time_not_push_time():
    report = atlas.build_report(research_run([hypothesis()]))
    rendered = report.render()
    assert "- run_started_at: 2026-07-27T04:00:00+00:00" in rendered
    assert "- code_revision: deadbeef" in rendered, "result hash pins reproducibility"
    assert atlas.build_report(research_run([hypothesis()])).render() == rendered


# ------------------------------------------------------- against real runs

@pytest.mark.integration
def test_a_real_run_produces_citable_findings(run, snapshot):
    found = atlas.findings_from(run, snapshot)
    assert len(found) >= len(run.hypotheses)
    assert len(set(found)) == len(found), "duplicate findings cannot be cited apart"
    for finding in found:
        assert "\n" not in finding and finding.strip()


@pytest.mark.integration
def test_a_real_run_builds_a_contract_shaped_report(run, snapshot):
    rendered = atlas.build_report(run, snapshot).render()
    lines = [ln for ln in rendered.splitlines() if ln.startswith("FINDING ")]
    assert lines
    for index, line in enumerate(lines, start=1):
        assert line.startswith(f"FINDING {index}: ")
    assert f"- module_version: {run.engine_version}" in rendered


@pytest.mark.integration
def test_retention_baseline_is_measured_from_the_backtest(snapshot, taxonomy):
    baseline = atlas.retention_null_model(
        snapshot, taxonomy, ["2021-12-31", "2022-06-30", "2022-12-31"])
    assert baseline is not None
    assert baseline["retained"] + baseline["disowned"] == baseline["ever_candidate"]
    if baseline["retention_rate"] is not None:
        assert 0.0 <= baseline["retention_rate"] <= 1.0


@pytest.mark.integration
def test_the_northstar_sweep_baseline_is_reported_unusable(snapshot, taxonomy):
    """This corpus yields one ever-candidate cluster and a 100% retention rate.

    n=1 at 100% is noise wearing a percentage sign — nothing can be compared
    against it. The measurement is still reported, but flagged unusable with the
    reason, rather than handed on as if it were a baseline.
    """
    baseline = atlas.retention_null_model(
        snapshot, taxonomy, ["2021-12-31", "2022-06-30", "2022-12-31"])
    assert baseline["ever_candidate"] < atlas.MIN_BASELINE_SAMPLE
    assert baseline["usable"] is False
    assert "樣本過小" in baseline["unusable_reason"]
    assert "基準不可用" in baseline["statement"]


@pytest.mark.unit
def test_an_unusable_baseline_blocks_predictions(monkeypatch):
    class FakeClient:
        def __init__(self, base_url):
            pass

        def ensure_workspace(self, name, description=""):
            return "ws_1"

        def submit_run(self, ws, report):
            return {"module_run_id": "mr_1", "source_id": "src_1", "report_hash": "h"}

        def cite_finding(self, run_id, index, text, **kw):
            return {"claim_id": f"claim_{index}", "evidence_id": f"ev_{index}"}

        def register_prediction(self, *a, **kw):
            raise AssertionError("must not register against an unusable baseline")

    monkeypatch.setattr(atlas, "AtlasClient", FakeClient)
    pushed = atlas.push_run(
        research_run([hypothesis()]), base_url="http://x",
        null_model={"usable": False, "unusable_reason": "樣本過小:只有 1 個。",
                    "statement": "基準不可用:樣本過小:只有 1 個。"})
    assert pushed["predictions"] == []
    assert "樣本過小" in pushed["predictions_skipped_reason"]
    assert pushed["findings"] > 0

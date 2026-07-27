"""Submit a research run to the Frontier Atlas mothership.

AURORA is the second fleet module. The contract lives in
frontier-atlas/MOTHERSHIP.md: the module submits an immutable, hashed run
report, the mothership stores it as a source, and every finding is quoted
verbatim out of it.

Two things this adapter takes seriously, because AURORA's whole value is that it
does not overclaim:

**Findings state what the run observed, never what it implies.** A cluster's
status, score and the engine's own reasons are facts about this run at this
cutoff. "This industry is forming" is not.

**A prediction without a baseline is not registered.** The mothership requires a
null model, and the only honest one here is AURORA's own empirical status
retention rate, measured by the backtest. Without a backtest we submit findings
only. Registering a prediction against an invented baseline would produce
exactly the decorative ledger the mothership exists to prevent.
"""
from __future__ import annotations

from ._vendor.atlas_client import AtlasClient, AtlasError, RunReport
from .backtest import run_backtest

__all__ = ["AtlasError", "findings_from", "build_report", "push_run",
           "retention_null_model", "MODULE_ID", "CANDIDATE_STATUS"]

MODULE_ID = "aurora"
DEFAULT_WORKSPACE = "Fleet"
CANDIDATE_STATUS = "INDUSTRY_CANDIDATE"

# Matches backtest.py: the same cluster is tracked across cutoffs by entity-set
# Jaccard. A resolution rule that cannot name its matching procedure is not
# mechanically checkable, so the threshold is stated explicitly in the rule.
CLUSTER_MATCH_JACCARD = 0.4

# Statuses that mean the engine later disowned a cluster it once called a
# candidate. Same set backtest.py uses to count false positives.
DISOWNED_STATUSES = ("HYPE_CLUSTER", "REJECTED", "INSUFFICIENT_EVIDENCE")

TOP_CLUSTERS = 8

# A retention rate measured over a handful of clusters is noise wearing a
# percentage sign. Measured on the Northstar corpus the sweep yields exactly one
# ever-candidate cluster and a 100% rate -- a baseline nothing can be compared
# against. Below this many clusters the baseline is reported as unusable and no
# prediction is registered, which is the same discipline the engine applies to
# itself: not enough evidence, no verdict.
MIN_BASELINE_SAMPLE = 5


def _clean(text: str) -> str:
    return " ".join(str(text).split())


def findings_from(run, snapshot=None) -> list[str]:
    """Facts about one research run, one self-contained sentence each."""
    out: list[str] = []
    cutoff = run.cutoff_date or "full"
    manifest = run.leakage_manifest or {}

    counts = getattr(snapshot, "counts", None) or {}
    entities = counts.get("entities")
    observations = manifest.get("included_observation_count")
    if isinstance(entities, int) and isinstance(observations, int):
        out.append(
            f"AURORA 在 cutoff={cutoff} 的執行中,從 {entities} 個實體與 "
            f"{observations} 筆納入觀察分出 {len(run.hypotheses)} 個群集。")
    else:
        out.append(f"AURORA 在 cutoff={cutoff} 的執行中分出 {len(run.hypotheses)} 個群集。")

    # Leakage accounting is only meaningful for a historical run.
    if run.cutoff_date:
        future = manifest.get("excluded_future_observation_count")
        undated = manifest.get("excluded_undated_observation_count")
        if isinstance(future, int) and isinstance(undated, int):
            out.append(
                f"為守住 cutoff={run.cutoff_date},本次排除了 {future} 筆晚於切點的觀察"
                f"與 {undated} 筆無日期的觀察。")

    for hypothesis in run.hypotheses[:TOP_CLUSTERS]:
        name = _clean(hypothesis.generated_name)
        out.append(
            f"群集「{name}」在 cutoff={cutoff} 被分類為 {hypothesis.status},"
            f"總分 {hypothesis.overall_score:.1f},信心區間 {hypothesis.confidence_band}。")

        # The engine's own stated reason, forwarded rather than paraphrased.
        if hypothesis.summary:
            out.append(f"群集「{name}」的分類理由是:{_clean(hypothesis.summary)}")

        similarity = (hypothesis.existing_industry_similarity or {}).get("similarity")
        if hypothesis.status == "EXISTING_INDUSTRY_VARIANT" and isinstance(similarity, (int, float)):
            out.append(
                f"群集「{name}」與既有產業分類的最高相似度為 {float(similarity):.2f},"
                f"因此被判為既有產業的變體而非新產業。")

        missing = list(hypothesis.missing_evidence or [])
        if missing:
            out.append(
                f"群集「{name}」目前完全沒有這幾類證據:{', '.join(missing)}。")

    return out


def retention_null_model(snapshot, taxonomy, cutoffs, cfg=None,
                         min_sample: int = MIN_BASELINE_SAMPLE) -> dict | None:
    """Empirical base rate for a candidate keeping its status, from the backtest.

    Returns None when no cutoffs were given — nothing was measured at all.
    Otherwise always returns the measurement, carrying `usable`: a baseline
    drawn from too few clusters is reported honestly as unusable rather than
    quietly handed over as a percentage. `push_run` registers predictions only
    against a usable baseline.
    """
    if not cutoffs:
        return None
    kwargs = {"cfg": cfg} if cfg is not None else {}
    result = run_backtest(snapshot, taxonomy, list(cutoffs), **kwargs)

    ever_candidate = [
        track for track in result["tracks"]
        if any(step["status"] == CANDIDATE_STATUS for step in track["history"])
    ]
    sweep = f"{result['cutoffs'][0]}..{result['cutoffs'][-1]}"
    disowned = [t for t in ever_candidate if t["final_status"] in DISOWNED_STATUSES]
    retained = len(ever_candidate) - len(disowned)
    rate = (retained / len(ever_candidate)) if ever_candidate else None

    usable = len(ever_candidate) >= min_sample
    if not ever_candidate:
        reason = f"cutoff 掃描 {sweep} 中沒有任何群集曾被判為 {CANDIDATE_STATUS},無從測量基準。"
    elif not usable:
        reason = (f"樣本過小:cutoff 掃描 {sweep} 中只有 {len(ever_candidate)} 個群集曾被判為 "
                  f"{CANDIDATE_STATUS}(門檻 {min_sample})。這種規模算出來的保留率沒有鑑別力,"
                  f"不能當基準。")
    else:
        reason = None

    return {
        "usable": usable,
        "unusable_reason": reason,
        "ever_candidate": len(ever_candidate),
        "retained": retained,
        "disowned": len(disowned),
        "retention_rate": round(rate, 4) if rate is not None else None,
        "min_sample": min_sample,
        "cutoffs": list(result["cutoffs"]),
        "statement": (
            f"經驗保留率基準:在 cutoff 掃描 {sweep} 中,"
            f"曾被判為 {CANDIDATE_STATUS} 的 {len(ever_candidate)} 個群集裡,"
            f"有 {retained} 個在全資料執行時仍未被引擎推翻,保留率 {rate:.0%}"
            f"(樣本數 {len(ever_candidate)})。優於此基準才算這次預測有資訊量。"
            if usable else f"基準不可用:{reason}"),
    }


def _prediction_statement(hypothesis, run) -> str:
    return (
        f"群集「{_clean(hypothesis.generated_name)}」"
        f"(entity_ids 共 {len(hypothesis.entity_ids)} 個,hypothesis_id={hypothesis.hypothesis_id})"
        f"在較晚的 cutoff 以相同引擎設定重跑後,仍會被分類為 {CANDIDATE_STATUS}。")


def _resolution_rule(run) -> str:
    return (
        f"以 engine={run.engine_version}、feature={run.feature_version}、"
        f"taxonomy={run.taxonomy_version} 的相同設定,在較晚的 cutoff 重跑 run_pipeline;"
        f"以 entity-set Jaccard >= {CLUSTER_MATCH_JACCARD} 比對出對應群集"
        f"(與 backtest.py 追蹤群集的方法相同),讀它的 status。"
        f"status 仍為 {CANDIDATE_STATUS} 判 correct;"
        f"落入 {'/'.join(DISOWNED_STATUSES)} 其一判 incorrect;"
        f"找不到 Jaccard >= {CLUSTER_MATCH_JACCARD} 的對應群集則判 ambiguous。")


def build_report(run, snapshot=None, *, inputs: str = "") -> RunReport:
    """Build the run report. Carries the run's OWN creation time, not push time.

    The mothership deduplicates on report content. A push-time stamp would make
    every re-push of the same run hash differently, so an unchanged run would be
    accepted again and again.
    """
    report = RunReport(
        MODULE_ID,
        module_version=run.engine_version,
        code_revision=run.result_manifest_hash,
        inputs=inputs or f"cutoff={run.cutoff_date or 'full'} snapshot={run.snapshot_id}",
        run_started_at=run.created_at)
    for finding in findings_from(run, snapshot):
        report.add_finding(finding)
    return report


def push_run(run, snapshot=None, *, base_url: str, workspace: str = DEFAULT_WORKSPACE,
             null_model: dict | None = None, horizon_days: int = 180,
             inputs: str = "") -> dict:
    """Submit a run; register predictions only when a measured baseline exists.

    Pass `null_model` from `retention_null_model(...)`. Without it the run's
    findings still land — they are observations and stand on their own — but no
    prediction is registered, because an unfalsifiable-in-practice prediction
    with a made-up baseline is worse than none.
    """
    report = build_report(run, snapshot, inputs=inputs)
    if len(report) == 0:
        raise AtlasError("這次執行沒有可陳述的發現,不提交空的 run report")

    client = AtlasClient(base_url)
    workspace_id = client.ensure_workspace(
        workspace, description="艦隊模組共用的證據工作區")
    submitted = client.submit_run(workspace_id, report)
    run_id = submitted["module_run_id"]

    findings = report.findings
    claims: dict[str, str] = {}
    for index, text in enumerate(findings, start=1):
        cited = client.cite_finding(run_id, index, text)
        claims[text] = cited["claim_id"]

    predictions = []
    skipped_reason = None
    if null_model is None:
        skipped_reason = ("沒有經驗基準率(未提供 backtest),依契約不登記預測——"
                          "沒有對照基準的預測不該進帳本。")
    elif not null_model.get("usable"):
        skipped_reason = ("經驗基準率不可用,依契約不登記預測:"
                          + str(null_model.get("unusable_reason") or "原因未記錄"))
    else:
        for hypothesis in run.hypotheses:
            if hypothesis.status != CANDIDATE_STATUS:
                continue
            anchor = next(
                (text for text in findings
                 if f"群集「{_clean(hypothesis.generated_name)}」" in text
                 and CANDIDATE_STATUS in text), None)
            if anchor is None:
                continue
            registered = client.register_prediction(
                run_id, claims[anchor],
                statement=_prediction_statement(hypothesis, run),
                resolution_rule=_resolution_rule(run),
                null_model=null_model["statement"],
                horizon_days=horizon_days)
            predictions.append(registered["id"])

    return {"workspace_id": workspace_id, "module_run_id": run_id,
            "source_id": submitted["source_id"],
            "report_hash": submitted["report_hash"],
            "findings": len(findings), "claims": len(claims),
            "predictions": predictions,
            "predictions_skipped_reason": skipped_reason}

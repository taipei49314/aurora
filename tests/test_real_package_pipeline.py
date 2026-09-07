"""Real offline package -> research run -> artifacts (the non-demo path).

Uses the committed real dataset (datasets/sodium-ion-us-2025): three real
companies, five public-domain government/patent records. Offline throughout.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aurora import DEFAULT_CONFIG, Taxonomy, import_package, run_pipeline
from aurora.packaging import (
    build_finding_traces,
    build_run_manifest,
    git_revision,
    load_package,
)

REAL_PACKAGE = (
    Path(__file__).resolve().parents[1]
    / "datasets" / "sodium-ion-us-2025" / "package.json"
)


@pytest.mark.integration
def test_real_package_loads_with_provenance():
    package, meta = load_package(REAL_PACKAGE)
    assert meta["dataset_id"] == "sodium-ion-us-2025"
    assert "Public domain" in meta["license"]
    assert len(meta["package_sha256"]) == 64
    assert len(package["sources"]) == 5
    assert all(row.get("url_or_local_path", "").startswith("https://")
               for row in package["sources"])


@pytest.mark.integration
def test_real_package_replay_is_deterministic(tmp_path):
    package, meta = load_package(REAL_PACKAGE)
    tax = Taxonomy.load(str(REAL_PACKAGE.parents[1] / "taxonomy" / "taxonomy.json"))

    anchored = import_package(package, created_at=meta.get("retrieved_at"))
    run1 = run_pipeline(anchored, tax, DEFAULT_CONFIG)
    run2 = run_pipeline(anchored, tax, DEFAULT_CONFIG)
    assert run1.run_id == run2.run_id
    assert run1.result_manifest_hash == run2.result_manifest_hash

    # A second import of the same bytes must land on the same manifest hash:
    reimported = import_package(package, created_at=meta.get("retrieved_at"))
    assert reimported.input_manifest_hash() == anchored.input_manifest_hash()
    assert reimported.snapshot_id == anchored.snapshot_id

    manifest = build_run_manifest(
        run1, anchored, meta, taxonomy_path="taxonomy",
        report_text="FINDING 1: x")
    assert manifest["deterministic"]["run_id"] == run1.run_id
    assert len(manifest["code_revision"]) in (0, 40)
    # The result hash must never masquerade as the code revision:
    assert manifest["code_revision"] != manifest["deterministic"]["result_manifest_hash"] \
        or manifest["code_revision"] == ""


@pytest.mark.integration
def test_real_package_traces_findings_to_sources(tmp_path):
    package, meta = load_package(REAL_PACKAGE)
    snap = import_package(package, created_at=meta.get("retrieved_at"))
    tax = Taxonomy.load(str(REAL_PACKAGE.parents[1] / "taxonomy" / "taxonomy.json"))
    run = run_pipeline(snap, tax, DEFAULT_CONFIG)

    traces = build_finding_traces(run, snap)
    assert traces, "the run produced hypotheses to trace"
    for trace in traces:
        assert trace["hypothesis_id"]
        assert "heuristic_confidence_band" in trace
        assert "engine_summary" in trace  # the engine's own stated reason
        assert "missing_evidence" in trace  # data gaps stay explicit
        for obs in trace["observations"]:
            assert obs["evidence_kind"] == "source_recorded_fact"
            assert obs["text_excerpt"]
            source = obs["source"]
            assert source and source["url_or_local_path"].startswith("https://")
            assert source["content_hash"]


@pytest.mark.integration
def test_cli_real_mode_writes_artifacts_and_rejects_mixed_inputs(tmp_path):
    from aurora.cli import main

    out_dir = tmp_path / "artifacts"
    code = main([
        "--package", str(REAL_PACKAGE),
        "--out-dir", str(out_dir),
    ])
    assert code is not None and code != 2
    assert (out_dir / "run.md").is_file()
    manifest = json.loads(
        (out_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["deterministic"]["package"]["dataset_id"] == "sodium-ion-us-2025"
    report = (out_dir / "run.md").read_text(encoding="utf-8")
    assert "信心區間" not in report
    findings = (out_dir / "findings.jsonl").read_text(encoding="utf-8").strip()
    assert findings
    for line in findings.splitlines():
        trace = json.loads(line)
        assert trace["hypothesis_id"]

    # Demo (--scale) and real (--package) inputs are never mixed:
    assert main([
        "--package", str(REAL_PACKAGE),
        "--scale", "0.01",
    ]) == 2

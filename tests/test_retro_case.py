"""Loop 3: iron-air-retro cutoff ledger gates."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_retro_case import run_case  # noqa: E402

CASE = ROOT / "cases" / "iron-air-retro"


@pytest.mark.integration
def test_iron_air_retro_ledger_passes():
    report = run_case(CASE)
    assert report["import_errors"] == 0
    assert report["passed"], report["failures"]
    assert len(report["cutoffs"]) == 3
    # early should not be candidate-class strong
    early = report["cutoffs"][0]
    assert early["leakage_violations"] == 0
    assert early["best_overall"] < 60
    late = report["cutoffs"][-1]
    assert late["best_overall"] >= early["best_overall"]
    assert late["manifest"]["excluded_future_observation_count"] == 0


@pytest.mark.unit
def test_ledger_honesty_present():
    ledger = json.loads((CASE / "ledger.json").read_text(encoding="utf-8"))
    assert ledger.get("honesty")
    assert "not scraped" in " ".join(ledger["honesty"]).lower() or any(
        "NOT scraped" in h or "not scraped" in h for h in ledger["honesty"]
    )

"""Company filings adapter tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import strip_package  # noqa: E402
from adapters.filings import convert_filings  # noqa: E402
from aurora import import_package  # noqa: E402

FIX = ROOT / "adapters" / "fixtures" / "filings_sample.json"


@pytest.mark.unit
def test_filings_fixture_types():
    raw = json.loads(FIX.read_text(encoding="utf-8"))
    pkg = convert_filings(raw)
    assert pkg["_adapter"]["filing_count"] == 3
    assert all(s["source_type"] == "COMPANY_FILING" for s in pkg["sources"])
    assert all(s["reliability_tier"] == "A" for s in pkg["sources"])
    types = {o["observation_type"] for o in pkg["observations"]}
    assert "CAPEX_ACTIVITY" in types
    assert "CAPACITY_EXPANSION" in types
    ferro = next(e for e in pkg["entities"] if e["canonical_name"] == "FerroGrid Power")
    assert any(x.get("system") == "lei" for x in ferro["external_ids"])


@pytest.mark.integration
def test_filings_import_clean():
    raw = json.loads(FIX.read_text(encoding="utf-8"))
    snap = import_package(strip_package(convert_filings(raw)))
    assert snap.import_errors == []
    assert snap.counts["sources"] == 3

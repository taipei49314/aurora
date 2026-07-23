"""Real-shaped example package must import cleanly (adapter contract)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aurora import import_package

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "real_mini_package.json"


@pytest.mark.integration
def test_real_mini_package_imports_without_row_errors():
    raw = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    package = {
        "entities": raw["entities"],
        "sources": raw["sources"],
        "observations": raw["observations"],
    }
    snap = import_package(package)
    assert snap.import_errors == []
    assert len(snap.entities) == len(package["entities"])
    assert len(snap.observations) == len(package["observations"])
    # Wire reprint shares independence_group → independent < raw
    assert snap.counts["independent_source_count"] < snap.counts["raw_source_count"]
    assert snap.counts["independent_source_count"] == 8
    assert snap.counts["raw_source_count"] == 10


@pytest.mark.integration
def test_real_mini_package_source_refs_all_resolve():
    raw = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    refs = {s["ref"] for s in raw["sources"]}
    for obs in raw["observations"]:
        assert obs["source_ref"] in refs, obs["source_ref"]

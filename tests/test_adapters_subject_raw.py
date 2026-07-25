"""Offline adapters materialize first-class mention provenance."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import (  # noqa: E402
    convert_filings,
    convert_jobs,
    convert_news,
    convert_openalex,
    convert_uspto,
    ensure_observation_raw_mentions,
)
from adapters.patentsview import convert_patentsview  # noqa: E402

FIX = ROOT / "adapters" / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


@pytest.mark.unit
@pytest.mark.parametrize(
    "convert,fixture",
    [
        (convert_uspto, "uspto_sample.json"),
        (convert_patentsview, "patentsview_sample.json"),
        (convert_jobs, "jobs_sample.json"),
        (convert_news, "news_sample.json"),
        (convert_filings, "filings_sample.json"),
        (convert_openalex, "openalex_sample.json"),
    ],
)
def test_all_offline_adapters_default_raw_mentions(convert, fixture):
    pkg = convert(_load(fixture))
    assert pkg["observations"]
    for observation in pkg["observations"]:
        assert observation["subject_raw"] == observation["subject"]
        if observation.get("object") not in (None, ""):
            assert observation["object_raw"] == observation["object"]


@pytest.mark.unit
def test_raw_mention_defaults_preserve_explicit_and_metadata_values():
    pkg = {
        "entities": [],
        "sources": [],
        "observations": [{
            "subject": "Canonical Co",
            "subject_raw": "Printed Co",
            "object": "Canonical Tech",
            "metadata": {"object_raw": "Printed Tech", "keep": True},
        }],
    }
    out = ensure_observation_raw_mentions(pkg)
    row = out["observations"][0]
    assert row["subject_raw"] == "Printed Co"
    assert row["object_raw"] == "Printed Tech"
    assert row["metadata"] == {"keep": True}
    assert pkg["observations"][0]["metadata"]["object_raw"] == "Printed Tech"

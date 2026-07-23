"""OpenAlex offline adapter tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import convert_openalex, strip_package  # noqa: E402
from adapters.openalex import _abstract_from_inverted  # noqa: E402
from aurora import import_package  # noqa: E402

FIX = ROOT / "adapters" / "fixtures" / "openalex_sample.json"


@pytest.mark.unit
def test_inverted_abstract_rebuild():
    idx = {"hello": [0], "world": [1]}
    assert _abstract_from_inverted(idx) == "hello world"


@pytest.mark.unit
def test_openalex_fixture_shape():
    raw = json.loads(FIX.read_text(encoding="utf-8"))
    pkg = convert_openalex(raw)
    assert pkg["_adapter"]["work_count"] == 2
    assert len(pkg["sources"]) == 2
    assert all(s["source_type"] == "PAPER" for s in pkg["sources"])
    assert any(o["observation_type"] == "RESEARCH_ACTIVITY" for o in pkg["observations"])
    names = {e["canonical_name"] for e in pkg["entities"]}
    assert "Grid Storage Research Lab" in names


@pytest.mark.unit
def test_openalex_authors_are_person_entities():
    raw = json.loads(FIX.read_text(encoding="utf-8"))
    pkg = convert_openalex(raw)
    people = [e for e in pkg["entities"] if e.get("entity_type") == "PERSON"]
    names = {e["canonical_name"] for e in people}
    assert "Alex Chen" in names
    assert "M. Schneider" in names
    # ORCID preserved when present
    alex = next(e for e in people if e["canonical_name"] == "Alex Chen")
    systems = {x.get("system") for x in alex.get("external_ids") or []}
    assert "orcid" in systems
    assert "openalex_author" in systems
    # institution observations still carry author list in metadata
    assert any(
        "Alex Chen" in (o.get("metadata") or {}).get("authors", [])
        for o in pkg["observations"]
    )


@pytest.mark.integration
def test_openalex_imports_clean():
    raw = json.loads(FIX.read_text(encoding="utf-8"))
    snap = import_package(strip_package(convert_openalex(raw)))
    assert snap.import_errors == []
    assert snap.counts["sources"] == 2
    # shared institution across two papers
    labs = [e for e in snap.entities if "Grid Storage" in e.canonical_name]
    assert labs
    assert any(x.get("system") == "openalex_org" for x in labs[0].external_ids)

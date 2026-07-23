"""Adapters emit first-class entity external_ids (not only metadata)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import convert_jobs, convert_uspto, strip_package  # noqa: E402
from adapters.patentsview import convert_patentsview  # noqa: E402
from aurora import import_package  # noqa: E402

FIX = ROOT / "adapters" / "fixtures"


@pytest.mark.unit
def test_uspto_assignee_external_ids_first_class():
    raw = {
        "patents": [{
            "publication_number": "US1",
            "title": "T",
            "abstract": "A",
            "application_date": "2020-01-01",
            "publication_date": "2021-01-01",
            "assignees": [{
                "name": "Acme Co",
                "country": "US",
                "lei": "LEI-ACME",
                "domain": "acme.example",
            }],
        }],
    }
    pkg = convert_uspto(raw)
    acme = next(e for e in pkg["entities"] if e["canonical_name"] == "Acme Co")
    assert "external_ids" in acme
    systems = {x["system"] for x in acme["external_ids"]}
    assert "lei" in systems
    assert "domain" in systems
    assert "external_ids" not in acme.get("metadata", {})


@pytest.mark.unit
def test_jobs_domain_first_class():
    pkg = convert_jobs(json.loads((FIX / "jobs_sample.json").read_text(encoding="utf-8")))
    ferro = next(e for e in pkg["entities"] if e["canonical_name"] == "FerroGrid Power")
    assert any(x.get("system") == "domain" for x in ferro.get("external_ids") or [])


@pytest.mark.integration
def test_patentsview_import_keeps_assignee_name_ext():
    pkg = convert_patentsview(
        json.loads((FIX / "patentsview_sample.json").read_text(encoding="utf-8"))
    )
    snap = import_package(strip_package(pkg))
    assert snap.import_errors == []
    # at least one company has uspto_assignee_name or similar external id
    ext_systems = {
        x.get("system")
        for e in snap.entities
        for x in (e.external_ids or [])
    }
    assert "uspto_assignee_name" in ext_systems

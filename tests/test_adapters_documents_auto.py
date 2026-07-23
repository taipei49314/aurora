"""Adapters auto-build documents[] from source excerpts (engine 0.1.19+)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from adapters import (  # noqa: E402
    convert_filings,
    convert_jobs,
    convert_news,
    convert_openalex,
    convert_uspto,
    ensure_documents,
    merge_packages,
    strip_package,
)
from adapters.package_util import package_stats  # noqa: E402
from adapters.patentsview import convert_patentsview  # noqa: E402
from aurora import import_package  # noqa: E402

FIX = ROOT / "adapters" / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


@pytest.mark.unit
def test_build_documents_from_uspto_fixture():
    pkg = convert_uspto(_load("uspto_sample.json"))
    docs = pkg.get("documents") or []
    assert docs, "adapter should auto-build documents[]"
    stats = package_stats(pkg)
    assert stats["documents"] == stats["sources"]
    assert stats["documents_with_text"] >= 1

    by_id = {d["document_id"]: d for d in docs}
    # document_id convention == source.ref
    for src in pkg["sources"]:
        ref = src["ref"]
        assert ref in by_id
        d = by_id[ref]
        assert d.get("source_ref") == ref
        assert d.get("title") == src.get("title")
        assert (d.get("text") or "").strip()
        assert (d.get("metadata") or {}).get("auto_built") is True
        assert (d.get("metadata") or {}).get("from") == "source_excerpt"

    # every observation document_id has a full document row
    for o in pkg["observations"]:
        did = o.get("document_id")
        if did:
            assert did in by_id


@pytest.mark.unit
def test_strip_package_keeps_documents():
    pkg = convert_uspto(_load("uspto_sample.json"))
    stripped = strip_package(pkg)
    assert "documents" in stripped
    assert len(stripped["documents"]) == len(pkg["documents"])
    assert "_adapter" not in stripped


@pytest.mark.unit
def test_ensure_documents_preserves_existing_text():
    base = {
        "entities": [],
        "sources": [{
            "ref": "src-a",
            "title": "Title A",
            "excerpt": "short excerpt",
        }],
        "observations": [{
            "source_ref": "src-a",
            "document_id": "src-a",
            "observation_type": "PATENT_ACTIVITY",
            "subject": "X",
        }],
        "documents": [{
            "document_id": "src-a",
            "source_ref": "src-a",
            "title": "Full title",
            "text": "This is the longer full text body that must be kept.",
            "metadata": {"manual": True},
        }],
    }
    out = ensure_documents(base)
    docs = out["documents"]
    assert len(docs) == 1
    assert docs[0]["text"].startswith("This is the longer")
    assert docs[0]["metadata"].get("manual") is True


@pytest.mark.unit
def test_merge_packages_merges_documents():
    a = convert_jobs(_load("jobs_sample.json"))
    b = convert_news(_load("news_sample.json"))
    merged = merge_packages([a, b])
    docs = merged.get("documents") or []
    assert docs
    ids = {d["document_id"] for d in docs}
    # job + news refs present
    assert any(i.startswith("job-") for i in ids)
    assert any(i.startswith("news-") for i in ids)
    stats = package_stats(merged)
    assert stats["documents"] == len(ids)
    assert stats["orphan_observations"] == 0


@pytest.mark.integration
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
def test_all_adapters_documents_import_clean(convert, fixture):
    pkg = convert(_load(fixture))
    assert pkg.get("documents"), f"{fixture}: expected auto documents[]"
    snap = import_package(strip_package(pkg))
    assert snap.import_errors == []
    assert len(snap.documents) >= 1
    # full rows, not stubs-only
    assert any((d.text or "").strip() for d in snap.documents)
    # obs document_ids resolve into snapshot documents
    doc_ids = {d.document_id for d in snap.documents}
    for o in snap.observations:
        if o.document_id:
            assert o.document_id in doc_ids

"""char_span auto-align from text_excerpt (engine 0.1.20+)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from adapters import convert_uspto, strip_package  # noqa: E402
from adapters.package_util import align_char_span, package_stats  # noqa: E402
from aurora.char_span import align_char_span as engine_align  # noqa: E402
from aurora import import_package  # noqa: E402

FIX = ROOT / "adapters" / "fixtures"


@pytest.mark.unit
def test_align_exact_and_case_and_whitespace():
    doc = "Hello world. Porous iron electrode enables storage."
    assert align_char_span(doc, "Porous iron electrode") == [13, 34]
    assert engine_align(doc, "Porous iron electrode") == [13, 34]

    # case-insensitive
    span = align_char_span(doc, "POROUS IRON ELECTRODE")
    assert span == [13, 34]

    # whitespace-flexible
    doc2 = "A porous   iron\nelectrode enables reversible oxidation."
    span2 = align_char_span(doc2, "porous iron electrode")
    assert span2 is not None
    assert "porous" in doc2[span2[0]:span2[1]].lower()

    assert align_char_span(doc, "zz") is None  # too short
    assert align_char_span(doc, "not present at all here") is None


@pytest.mark.unit
def test_align_progressive_prefix_near_match():
    """0.1.24+: trailing-clause / punctuation drift still yields a span."""
    doc = (
        "Laboratory review of reversible iron oxidation pathways and "
        "porous electrode limits for multi-day grid storage concepts."
    )
    ex = (
        "Laboratory review of reversible iron oxidation pathways and "
        "porous electrode limits for multi-day grid storage."
    )
    span = align_char_span(doc, ex)
    assert span is not None
    assert span == engine_align(doc, ex)
    a, b = span
    assert "Laboratory review" in doc[a:b]
    assert b - a >= 12

    # Case-insensitive progressive on title-ish vs abstract
    doc2 = "A porous iron electrode enables reversible iron oxidation for storage."
    ex2 = "Porous iron electrode for reversible iron oxidation and hundred-hour duty"
    span2 = align_char_span(doc2, ex2)
    assert span2 is not None
    assert "porous iron electrode" in doc2[span2[0] : span2[1]].lower()


@pytest.mark.unit
def test_import_auto_aligns_missing_char_span():
    pkg = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [{
            "ref": "src1",
            "source_type": "PATENT",
            "publisher": "USPTO",
            "title": "Iron-air cell",
            "excerpt": "Full abstract of the iron-air invention goes here.",
            "published_at": "2022-01-01",
        }],
        "documents": [{
            "document_id": "doc-1",
            "source_ref": "src1",
            "title": "Iron-air cell",
            "text": "Full abstract of the iron-air invention goes here. More claims follow.",
        }],
        "observations": [{
            "source_ref": "src1",
            "observation_type": "PATENT_ACTIVITY",
            "subject": "Acme",
            "observed_at": "2021-06-01",
            "text_excerpt": "Full abstract of the iron-air invention goes here.",
            "document_id": "doc-1",
            # no char_span — should auto-align
        }],
    }
    snap = import_package(pkg)
    assert snap.import_errors == []
    assert len(snap.observations) == 1
    obs = snap.observations[0]
    assert obs.char_span == [0, 50]
    assert (obs.metadata or {}).get("char_span_auto") is True
    assert snap.counts.get("char_spans_auto_aligned") == 1


@pytest.mark.unit
def test_import_preserves_explicit_char_span():
    pkg = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [{
            "ref": "src1",
            "source_type": "PATENT",
            "publisher": "USPTO",
            "title": "T",
            "excerpt": "abcdef",
            "published_at": "2022-01-01",
        }],
        "documents": [{
            "document_id": "doc-1",
            "text": "xxx abcdef yyy",
        }],
        "observations": [{
            "source_ref": "src1",
            "observation_type": "PATENT_ACTIVITY",
            "subject": "Acme",
            "observed_at": "2021-06-01",
            "text_excerpt": "abcdef",
            "document_id": "doc-1",
            "char_span": [4, 10],
        }],
    }
    snap = import_package(pkg)
    assert snap.observations[0].char_span == [4, 10]
    assert snap.counts.get("char_spans_auto_aligned") == 0
    assert not (snap.observations[0].metadata or {}).get("char_span_auto")


@pytest.mark.integration
def test_retro_package_has_majority_char_spans():
    """iron-air-retro: progressive align + append_unmatched → near-full span coverage."""
    pkg_path = ROOT / "cases" / "iron-air-retro" / "package.json"
    if not pkg_path.is_file():
        pytest.skip("retro package missing")
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    snap = import_package({
        "entities": pkg.get("entities") or [],
        "sources": pkg.get("sources") or [],
        "observations": pkg.get("observations") or [],
        "documents": pkg.get("documents") or [],
    })
    assert snap.import_errors == []
    with_span = sum(1 for o in snap.observations if o.char_span is not None)
    assert with_span == len(snap.observations)
    assert len(snap.documents) >= 1


@pytest.mark.integration
def test_uspto_adapter_emits_aligned_spans():
    raw = json.loads((FIX / "uspto_sample.json").read_text(encoding="utf-8"))
    pkg = convert_uspto(raw)
    stats = package_stats(pkg)
    assert stats["documents"] >= 1
    assert stats["observations_with_char_span"] >= 1

    # Primary PATENT_ACTIVITY uses abstract[:400] inside abstract[:800] document
    patent_obs = [
        o for o in pkg["observations"]
        if o["observation_type"] == "PATENT_ACTIVITY" and o.get("char_span")
    ]
    assert patent_obs, "expected at least one auto-aligned PATENT_ACTIVITY span"
    for o in patent_obs:
        assert (o.get("metadata") or {}).get("char_span_auto") is True
        a, b = o["char_span"]
        assert 0 <= a < b

    snap = import_package(strip_package(pkg))
    assert snap.import_errors == []
    # Adapter already set spans → import should not double-count auto-align
    # (existing span preserved; char_span_auto may remain from adapter)
    with_span = sum(1 for o in snap.observations if o.char_span is not None)
    assert with_span >= len(patent_obs)

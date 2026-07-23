"""lint_package document_id / documents[] policy (engine 0.1.22+)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "scripts" / "lint_package.py"


def _run(pkg_path: Path, *flags: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "backend") + os.pathsep + str(ROOT)
    return subprocess.run(
        [sys.executable, str(LINT), str(pkg_path), *flags],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.mark.unit
def test_require_documents_fails_on_orphan_document_id(tmp_path):
    pkg = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [{
            "ref": "s1",
            "source_type": "PATENT",
            "publisher": "USPTO",
            "title": "T",
            "excerpt": "body text here",
            "license": "public-patent-text",
        }],
        "observations": [{
            "source_ref": "s1",
            "observation_type": "PATENT_ACTIVITY",
            "subject": "Acme",
            "observed_at": "2020-01-01",
            "text_excerpt": "body text",
            "document_id": "orphan-doc-1",
        }],
        # no documents[]
    }
    p = tmp_path / "orphan.json"
    p.write_text(json.dumps(pkg), encoding="utf-8")

    # soft: ok without flag, but reports orphan
    r = _run(p, "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    body = json.loads(r.stdout)
    assert body["ok"] is True
    assert body["orphan_document_id_count"] == 1
    assert "orphan-doc-1" in body["orphan_document_ids"]
    assert body["document_ids_referenced"] == 1
    assert body["documents_total"] == 0

    # hard: fail with --require-documents
    r2 = _run(p, "--require-documents", "--json")
    assert r2.returncode != 0
    body2 = json.loads(r2.stdout)
    assert body2["ok"] is False
    assert any("orphan-doc-1" in i or "document_id" in i for i in body2["issues"])


@pytest.mark.unit
def test_require_documents_passes_when_documents_present(tmp_path):
    pkg = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [{
            "ref": "s1",
            "source_type": "PATENT",
            "publisher": "USPTO",
            "title": "Iron cell",
            "excerpt": "Full abstract of the iron-air invention goes here.",
            "license": "public-patent-text",
        }],
        "documents": [{
            "document_id": "doc-1",
            "source_ref": "s1",
            "title": "Iron cell",
            "text": "Full abstract of the iron-air invention goes here. Claims.",
            "license": "public-patent-text",
        }],
        "observations": [{
            "source_ref": "s1",
            "observation_type": "PATENT_ACTIVITY",
            "subject": "Acme",
            "observed_at": "2020-01-01",
            "text_excerpt": "Full abstract of the iron-air invention goes here.",
            "document_id": "doc-1",
        }],
    }
    p = tmp_path / "ok_docs.json"
    p.write_text(json.dumps(pkg), encoding="utf-8")
    r = _run(p, "--require-documents", "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    body = json.loads(r.stdout)
    assert body["ok"] is True
    assert body["orphan_document_id_count"] == 0
    assert body["documents_total"] == 1
    assert body["documents_with_text"] == 1
    assert body["observations_with_document_id"] >= 1
    # auto-align should fill span
    assert body["observations_with_char_span"] >= 1


@pytest.mark.unit
@pytest.mark.parametrize(
    "rel",
    [
        "cases/multisource-iron-air/package.json",
        "cases/iron-air-mini/package.json",
        "cases/iron-air-retro/package.json",
        "cases/openalex-sample/package.json",
        "cases/patentsview-sample/package.json",
        "examples/real_mini_package.json",
    ],
)
def test_case_packages_require_documents(rel):
    """Adapter-regenerated and curated cases ship documents[] without orphans."""
    pkg = ROOT / rel
    if not pkg.is_file():
        pytest.skip(f"{rel} missing")
    r = _run(pkg, "--require-documents", "--json", "--strict")
    assert r.returncode == 0, r.stdout + r.stderr
    body = json.loads(r.stdout)
    assert body["orphan_document_id_count"] == 0
    assert body["documents_total"] >= 1


@pytest.mark.unit
def test_require_char_spans_fails_when_missing(tmp_path):
    """0.1.26+: --require-char-spans fails when document_id obs has no span."""
    pkg = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [{
            "ref": "s1",
            "source_type": "PATENT",
            "publisher": "USPTO",
            "title": "T",
            "excerpt": "short abstract body text here for patent",
            "license": "public-patent-text",
        }],
        "documents": [{
            "document_id": "s1",
            "source_ref": "s1",
            "text": "short abstract body text here for patent",
        }],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "PATENT_ACTIVITY",
                "subject": "Acme",
                "observed_at": "2020-01-01",
                "text_excerpt": "short abstract body text here for patent",
                "document_id": "s1",
                # will auto-align
            },
            {
                "source_ref": "s1",
                "observation_type": "TECHNICAL_DEPENDENCY",
                "subject": "Acme",
                "object": "Acme",
                "observed_at": "2020-01-01",
                "text_excerpt": "zzz totally missing from document xyz",
                "document_id": "s1",
                # no align possible
            },
        ],
    }
    p = tmp_path / "no_span.json"
    p.write_text(json.dumps(pkg), encoding="utf-8")

    # soft: reports missing but ok
    r = _run(p, "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    body = json.loads(r.stdout)
    assert body["ok"] is True
    assert body["observations_missing_char_span"] >= 1
    assert "char_span_ratio" in body

    r2 = _run(p, "--require-char-spans", "--json")
    assert r2.returncode != 0
    body2 = json.loads(r2.stdout)
    assert body2["ok"] is False
    assert any("char_span" in i for i in body2["issues"])


@pytest.mark.unit
def test_min_char_span_ratio_fails_below_floor(tmp_path):
    pkg = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [{
            "ref": "s1",
            "source_type": "NEWS",
            "publisher": "P",
            "title": "T",
            "excerpt": "hello world excerpt body",
        }],
        "documents": [{
            "document_id": "s1",
            "text": "hello world excerpt body",
        }],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "ADOPTION_SIGNAL",
                "subject": "Acme",
                "observed_at": "2020-01-01",
                "text_excerpt": "hello world excerpt body",
                "document_id": "s1",
            },
            {
                "source_ref": "s1",
                "observation_type": "DEMAND_SIGNAL",
                "subject": "Acme",
                "observed_at": "2020-01-01",
                "text_excerpt": "no match for this claim",
                "document_id": "s1",
            },
        ],
    }
    p = tmp_path / "ratio.json"
    p.write_text(json.dumps(pkg), encoding="utf-8")
    r = _run(p, "--min-char-span-ratio", "0.9", "--json")
    assert r.returncode != 0
    body = json.loads(r.stdout)
    assert body["ok"] is False
    assert body["char_span_ratio"] < 0.9


@pytest.mark.unit
def test_retro_passes_require_char_spans():
    pkg = ROOT / "cases" / "iron-air-retro" / "package.json"
    if not pkg.is_file():
        pytest.skip("retro missing")
    r = _run(pkg, "--require-documents", "--require-char-spans", "--json", "--strict")
    assert r.returncode == 0, r.stdout + r.stderr
    body = json.loads(r.stdout)
    assert body["observations_missing_char_span"] == 0
    assert body["char_span_ratio"] >= 0.99

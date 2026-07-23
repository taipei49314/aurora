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

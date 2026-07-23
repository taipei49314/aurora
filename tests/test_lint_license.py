"""lint_package public-corpus license policy (engine 0.1.14+)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "scripts" / "lint_package.py"


def _run(pkg_path: Path, *flags: str) -> subprocess.CompletedProcess:
    import os

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
def test_require_license_fails_when_missing(tmp_path):
    pkg = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [
            {
                "ref": "a",
                "source_type": "NEWS",
                "publisher": "P",
                "title": "No license",
                "excerpt": "x",
            }
        ],
        "observations": [],
    }
    p = tmp_path / "no_lic.json"
    p.write_text(json.dumps(pkg), encoding="utf-8")
    r = _run(p, "--require-license", "--json")
    assert r.returncode != 0
    body = json.loads(r.stdout)
    assert body["ok"] is False
    assert body["sources_missing_license"] == 1


@pytest.mark.unit
def test_public_corpus_passes_with_licenses(tmp_path):
    pkg = {
        "license": "cc-by-4.0",
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [
            {
                "ref": "a",
                "source_type": "NEWS",
                "publisher": "P",
                "title": "Has package license",
                "excerpt": "x",
            }
        ],
        "observations": [],
    }
    p = tmp_path / "ok_lic.json"
    p.write_text(json.dumps(pkg), encoding="utf-8")
    r = _run(p, "--public-corpus", "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    body = json.loads(r.stdout)
    assert body["ok"] is True
    assert body["sources_with_license"] == 1
    assert body["license_counts"].get("cc-by-4.0") == 1

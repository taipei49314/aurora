"""Scorecard gates for char_span coverage (engine 0.1.25+)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts" / "check_case_scorecard.py"


def _run(case_dir: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "backend") + os.pathsep + str(ROOT)
    return subprocess.run(
        [sys.executable, str(CHECK), str(case_dir)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.mark.unit
def test_scorecard_fails_when_span_floor_not_met(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    pkg = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [{
            "ref": "s1",
            "source_type": "PATENT",
            "publisher": "USPTO",
            "title": "T",
            "excerpt": "body text for the patent abstract",
            "published_at": "2020-01-01",
        }],
        "documents": [{
            "document_id": "s1",
            "source_ref": "s1",
            "text": "body text for the patent abstract",
        }],
        "observations": [{
            "source_ref": "s1",
            "observation_type": "PATENT_ACTIVITY",
            "subject": "Acme",
            "observed_at": "2020-01-01",
            "text_excerpt": "body text for the patent abstract",
            "document_id": "s1",
            "char_span": [0, 10],
        }, {
            "source_ref": "s1",
            "observation_type": "TECHNICAL_DEPENDENCY",
            "subject": "Acme",
            "object": "Acme",
            "observed_at": "2020-01-01",
            "text_excerpt": "completely unrelated claim not in body",
            "document_id": "s1",
            # no char_span and won't auto-align
        }],
    }
    (case / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
    (case / "scorecard.json").write_text(json.dumps({
        "case_id": "tmp",
        "gates": {
            "import_errors_max": 0,
            "min_observations_with_char_span": 2,
            "min_char_span_ratio": 1.0,
        },
    }), encoding="utf-8")
    r = _run(case)
    assert r.returncode != 0
    out = r.stdout + r.stderr
    assert "min_observations_with_char_span" in out or "min_char_span_ratio" in out


@pytest.mark.integration
@pytest.mark.parametrize(
    "case_name",
    [
        "iron-air-mini",
        "iron-air-retro",
        "multisource-iron-air",
        "openalex-sample",
        "patentsview-sample",
    ],
)
def test_case_scorecards_pass_span_gates(case_name):
    case = ROOT / "cases" / case_name
    if not (case / "scorecard.json").is_file():
        pytest.skip("no scorecard")
    r = _run(case)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK: scorecard gates passed" in r.stdout

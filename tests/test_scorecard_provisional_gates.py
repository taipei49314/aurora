"""Scorecard gates for provisional entities (engine 0.1.41+)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts" / "check_case_scorecard.py"
LINT = ROOT / "scripts" / "lint_package.py"


def _env() -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "backend") + os.pathsep + str(ROOT)
    return env


def _run_scorecard(case_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECK), str(case_dir)],
        cwd=str(ROOT),
        env=_env(),
        capture_output=True,
        text=True,
    )


@pytest.mark.unit
def test_scorecard_require_no_provisional_fails(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    pkg = {
        "stage_unresolved": True,
        "entities": [],
        "sources": [{
            "ref": "s1",
            "source_type": "NEWS",
            "publisher": "Wire",
            "title": "T",
            "published_at": "2020-01-01",
        }],
        "observations": [{
            "source_ref": "s1",
            "observation_type": "HIRING_ACTIVITY",
            "subject": "Ghost Co",
            "observed_at": "2020-01-01",
            "text_excerpt": "hiring",
        }],
    }
    (case / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
    (case / "scorecard.json").write_text(json.dumps({
        "case_id": "tmp-prov",
        "gates": {
            "import_errors_max": 0,
            "require_no_provisional": True,
        },
    }), encoding="utf-8")
    r = _run_scorecard(case)
    assert r.returncode != 0
    out = r.stdout + r.stderr
    assert "provisional" in out.lower()
    assert "Ghost Co" in out


@pytest.mark.unit
def test_scorecard_max_provisional_entities(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    pkg = {
        "entities": [{
            "entity_type": "PROVISIONAL",
            "canonical_name": "Staged One",
            "metadata": {"provisional": True},
        }],
        "sources": [],
        "observations": [],
    }
    (case / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
    (case / "scorecard.json").write_text(json.dumps({
        "case_id": "tmp-max",
        "gates": {
            "import_errors_max": 0,
            "max_provisional_entities": 0,
        },
    }), encoding="utf-8")
    r = _run_scorecard(case)
    assert r.returncode != 0
    assert "max_provisional_entities" in (r.stdout + r.stderr)


@pytest.mark.unit
def test_scorecard_require_no_provisional_passes_resolved(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    pkg = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [],
        "observations": [],
    }
    (case / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
    (case / "scorecard.json").write_text(json.dumps({
        "case_id": "tmp-ok",
        "gates": {
            "import_errors_max": 0,
            "require_no_provisional": True,
        },
    }), encoding="utf-8")
    r = _run_scorecard(case)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.unit
def test_example_lint_no_provisional_passes():
    env = _env()
    r = subprocess.run(
        [
            sys.executable,
            str(LINT),
            str(ROOT / "examples" / "real_mini_package.json"),
            "--strict",
            "--require-documents",
            "--no-provisional",
            "--json",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    body = json.loads(r.stdout)
    assert body["provisional_entities"] == 0


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
def test_curated_cases_have_no_provisional(case_name):
    case = ROOT / "cases" / case_name
    sc = json.loads((case / "scorecard.json").read_text(encoding="utf-8"))
    assert sc["gates"].get("require_no_provisional") is True
    r = _run_scorecard(case)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "provisional=0" in r.stdout

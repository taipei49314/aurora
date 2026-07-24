"""lint_package --no-provisional and resolve_entities promote (engine 0.1.40+)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "scripts" / "lint_package.py"
RESOLVE = ROOT / "scripts" / "resolve_entities.py"


def _env() -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "backend") + os.pathsep + str(ROOT)
    return env


def _run(script: Path, *args: str, input_text=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(ROOT),
        env=_env(),
        capture_output=True,
        text=True,
        input=input_text,
    )


@pytest.mark.unit
def test_lint_soft_reports_provisional(tmp_path):
    pkg = {
        "stage_unresolved": True,
        "entities": [],
        "sources": [
            {
                "ref": "s1",
                "source_type": "NEWS",
                "publisher": "Wire",
                "title": "T",
                "published_at": "2020-01-01",
            }
        ],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "HIRING_ACTIVITY",
                "subject": "Ghost Co",
                "observed_at": "2020-01-01",
                "text_excerpt": "hiring",
            }
        ],
    }
    p = tmp_path / "stage.json"
    p.write_text(json.dumps(pkg), encoding="utf-8")
    r = _run(LINT, str(p), "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    body = json.loads(r.stdout)
    assert body["ok"] is True
    assert body["provisional_entities"] == 1
    assert "Ghost Co" in body["provisional_entity_names"]


@pytest.mark.unit
def test_lint_no_provisional_fails(tmp_path):
    pkg = {
        "stage_unresolved": True,
        "entities": [],
        "sources": [
            {
                "ref": "s1",
                "source_type": "NEWS",
                "publisher": "Wire",
                "title": "T",
                "published_at": "2020-01-01",
            }
        ],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "HIRING_ACTIVITY",
                "subject": "Ghost Co",
                "observed_at": "2020-01-01",
                "text_excerpt": "hiring",
            }
        ],
    }
    p = tmp_path / "stage.json"
    p.write_text(json.dumps(pkg), encoding="utf-8")
    r = _run(LINT, str(p), "--no-provisional", "--json")
    assert r.returncode != 0
    body = json.loads(r.stdout)
    assert body["ok"] is False
    assert body["provisional_entities"] == 1
    assert any("provisional" in i.lower() for i in body["issues"])


@pytest.mark.unit
def test_lint_no_provisional_passes_clean_package(tmp_path):
    pkg = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [],
        "observations": [],
    }
    p = tmp_path / "clean.json"
    p.write_text(json.dumps(pkg), encoding="utf-8")
    r = _run(LINT, str(p), "--forbid-provisional", "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    body = json.loads(r.stdout)
    assert body["provisional_entities"] == 0


@pytest.mark.unit
def test_resolve_list_provisional(tmp_path):
    pkg = {
        "stage_unresolved": True,
        "entities": [],
        "sources": [
            {
                "ref": "s1",
                "source_type": "NEWS",
                "publisher": "Wire",
                "title": "T",
                "published_at": "2020-01-01",
            }
        ],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "HIRING_ACTIVITY",
                "subject": "Ghost Co",
                "observed_at": "2020-01-01",
                "text_excerpt": "hiring",
            }
        ],
    }
    p = tmp_path / "stage.json"
    p.write_text(json.dumps(pkg), encoding="utf-8")
    r = _run(RESOLVE, str(p), "--list-provisional", "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    rows = json.loads(r.stdout)
    assert len(rows) == 1
    assert rows[0]["canonical_name"] == "Ghost Co"
    assert rows[0]["provisional"] is True


@pytest.mark.unit
def test_resolve_promote_writes_entity_and_lint_clean(tmp_path):
    pkg = {
        "stage_unresolved": True,
        "entities": [],
        "sources": [
            {
                "ref": "s1",
                "source_type": "NEWS",
                "publisher": "Wire",
                "title": "T",
                "published_at": "2020-01-01",
            }
        ],
        "observations": [
            {
                "source_ref": "s1",
                "observation_type": "HIRING_ACTIVITY",
                "subject": "Ghost Co",
                "observed_at": "2020-01-01",
                "text_excerpt": "hiring",
            }
        ],
    }
    p = tmp_path / "stage.json"
    out = tmp_path / "promoted.json"
    p.write_text(json.dumps(pkg), encoding="utf-8")
    r = _run(
        RESOLVE,
        str(p),
        "--promote",
        "Ghost Co",
        "--to-type",
        "COMPANY",
        "--clear-stage-flag",
        "-o",
        str(out),
        "--json",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    promoted = json.loads(out.read_text(encoding="utf-8"))
    assert "stage_unresolved" not in promoted
    ents = [e for e in promoted["entities"] if e["canonical_name"] == "Ghost Co"]
    assert len(ents) == 1
    assert ents[0]["entity_type"] == "COMPANY"
    # re-lint with --no-provisional should pass (no staging, real entity)
    r2 = _run(LINT, str(out), "--no-provisional", "--json")
    assert r2.returncode == 0, r2.stdout + r2.stderr
    body = json.loads(r2.stdout)
    assert body["provisional_entities"] == 0

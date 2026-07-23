"""Shared pytest fixtures. Adds backend + dataset generator to sys.path and
provides cached snapshot / taxonomy / run objects. Ground truth is loaded ONLY
inside tests (never by the engine) — see test_ground_truth_isolation.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "datasets" / "northstar"))

import generate  # noqa: E402
from aurora import import_package, Taxonomy, run_pipeline, DEFAULT_CONFIG  # noqa: E402

TAXONOMY_PATH = ROOT / "datasets" / "taxonomy" / "taxonomy.json"
GROUND_TRUTH_PATH = ROOT / "tests" / "ground_truth" / "labels.json"


@pytest.fixture(scope="session")
def package():
    pkg, _gt = generate.generate()
    return pkg


@pytest.fixture(scope="session")
def ground_truth():
    _pkg, gt = generate.generate()
    return gt


@pytest.fixture(scope="session")
def snapshot(package):
    return import_package(package)


@pytest.fixture(scope="session")
def taxonomy():
    return Taxonomy.load(TAXONOMY_PATH)


@pytest.fixture(scope="session")
def run(snapshot, taxonomy):
    return run_pipeline(snapshot, taxonomy, DEFAULT_CONFIG)


@pytest.fixture(scope="session")
def fast_snapshot():
    """A small-scale snapshot used by heavy tests (50x determinism). Determinism
    and formula properties hold at any scale, so this keeps the suite quick."""
    pkg, _gt = generate.generate(scale=0.25)
    return import_package(pkg)


@pytest.fixture(scope="session")
def name_to_entity(snapshot):
    return {e.canonical_name: e.entity_id for e in snapshot.entities}


def hyp_for(run, entity_names, name_to_entity):
    """Find the hypothesis whose entity set best overlaps the given names."""
    target = {name_to_entity[n] for n in entity_names if n in name_to_entity}
    best, best_overlap = None, -1
    for h in run.hypotheses:
        overlap = len(target & set(h.entity_ids))
        if overlap > best_overlap:
            best, best_overlap = h, overlap
    return best

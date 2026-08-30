"""Source-ref collision safety and lossless same-content provenance merging."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.package_util import merge_packages  # noqa: E402
from aurora import import_package  # noqa: E402
import aurora.importing as importing_module  # noqa: E402


pytestmark = pytest.mark.unit
CREATED_AT = "2024-02-01T00:00:00+00:00"


def _source(*, ref: str, title: str = "Shared report", url: str = "", license: str = "") -> dict:
    return {
        "ref": ref,
        "source_type": "NEWS",
        "publisher": "Example Wire",
        "title": title,
        "published_at": "2024-01-01",
        "retrieved_at": "2024-01-02T00:00:00+00:00",
        "excerpt": "Acme launched the same product.",
        "url_or_local_path": url,
        "license": license,
    }


def _package(source: dict) -> dict:
    return {"entities": [], "sources": [source], "observations": []}


def test_package_merge_fails_closed_for_same_ref_with_different_content():
    left = _package(_source(ref="shared", title="First report"))
    right = _package(_source(ref="shared", title="Unrelated report"))

    with pytest.raises(ValueError, match="source ref collision.*different content"):
        merge_packages([left, right])


def test_package_merge_exact_duplicate_ref_stays_a_single_plain_source():
    source = _source(ref="same", url="https://example.test/a", license="cc-by-4.0")

    merged = merge_packages([_package(source), _package(copy.deepcopy(source))])

    assert len(merged["sources"]) == 1
    assert "provenance_aliases" not in merged["sources"][0].get("metadata", {})


def test_package_merge_preserves_same_content_provenance_variants():
    left = _source(ref="shared", url="https://one.test/report", license="cc-by-4.0")
    left["metadata"] = {"corpus_lineage": {"dataset_id": "corpus-one"}}
    right = _source(ref="shared", url="https://two.test/report", license="cc0-1.0")
    right["metadata"] = {"corpus_lineage": {"dataset_id": "corpus-two"}}

    merged = merge_packages([_package(left), _package(right)])
    reversed_merged = merge_packages([_package(right), _package(left)])
    aliases = merged["sources"][0]["metadata"]["provenance_aliases"]

    assert len(merged["sources"]) == 1
    assert merged["sources"] == reversed_merged["sources"]
    assert {alias["url_or_local_path"] for alias in aliases} == {
        "https://one.test/report",
        "https://two.test/report",
    }
    assert {alias["license"] for alias in aliases} == {"cc-by-4.0", "cc0-1.0"}
    assert {
        alias["metadata"]["corpus_lineage"]["dataset_id"] for alias in aliases
    } == {"corpus-one", "corpus-two"}


def test_remerging_provenance_aliases_is_idempotent_without_metadata():
    left = _source(ref="shared", url="https://one.test/report", license="cc-by-4.0")
    right = _source(ref="shared", url="https://two.test/report", license="cc0-1.0")

    merged = merge_packages([_package(left), _package(right)])
    remerged = merge_packages([merged, copy.deepcopy(merged)])

    assert remerged == merged
    assert len(remerged["sources"][0]["metadata"]["provenance_aliases"]) == 2

    snapshot = import_package(merged, created_at=CREATED_AT)
    imported_aliases = snapshot.sources[0].metadata["provenance_aliases"]
    assert len(imported_aliases) == 2
    assert all("metadata" not in alias for alias in imported_aliases)


def _direct_import_package() -> dict:
    first = _source(ref="alpha", url="https://one.test/report", license="cc-by-4.0")
    first["metadata"] = {"corpus_lineage": {"dataset_id": "corpus-one"}}
    second = _source(ref="beta", url="https://two.test/report", license="cc0-1.0")
    second["retrieved_at"] = "2024-01-03T00:00:00+00:00"
    second["metadata"] = {"corpus_lineage": {"dataset_id": "corpus-two"}}
    return {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [first, second],
        "observations": [
            {
                "source_ref": "alpha",
                "observation_type": "PRODUCT_LAUNCH",
                "subject": "Acme",
                "text_excerpt": "first observation",
            },
            {
                "source_ref": "beta",
                "observation_type": "PRODUCT_LAUNCH",
                "subject": "Acme",
                "text_excerpt": "second observation",
            },
        ],
    }


def test_importer_collapses_same_content_but_preserves_all_provenance_and_refs():
    package = _direct_import_package()

    snapshot = import_package(package, created_at=CREATED_AT)
    source = snapshot.sources[0]
    aliases = source.metadata["provenance_aliases"]

    assert snapshot.import_errors == []
    assert snapshot.counts["sources"] == 1
    assert len(snapshot.observations) == 2
    assert {observation.source_id for observation in snapshot.observations} == {
        source.source_id
    }
    assert {alias["ref"] for alias in aliases} == {"alpha", "beta"}
    assert {alias["url_or_local_path"] for alias in aliases} == {
        "https://one.test/report",
        "https://two.test/report",
    }
    assert {alias["license"] for alias in aliases} == {"cc-by-4.0", "cc0-1.0"}
    assert {
        alias["metadata"]["corpus_lineage"]["dataset_id"] for alias in aliases
    } == {"corpus-one", "corpus-two"}


def test_same_content_provenance_merge_is_input_order_deterministic():
    package = _direct_import_package()
    reversed_package = copy.deepcopy(package)
    reversed_package["sources"].reverse()
    reversed_package["observations"].reverse()

    forward = import_package(package, created_at=CREATED_AT)
    reverse = import_package(reversed_package, created_at=CREATED_AT)

    assert forward.input_manifest_hash() == reverse.input_manifest_hash()
    assert vars(forward.sources[0]) == vars(reverse.sources[0])


def test_importer_invalidates_ambiguous_ref_instead_of_last_write_binding():
    package = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [
            _source(ref="collision", title="First report"),
            _source(ref="collision", title="Unrelated report"),
        ],
        "observations": [
            {
                "source_ref": "collision",
                "observation_type": "PRODUCT_LAUNCH",
                "subject": "Acme",
            }
        ],
    }

    snapshot = import_package(package, created_at=CREATED_AT)
    codes = {error["error_code"] for error in snapshot.import_errors}

    assert "SOURCE_REF_COLLISION" in codes
    assert snapshot.observations == []


def test_importer_invalidates_ref_on_truncated_source_id_collision(monkeypatch):
    real_prefixed_id = importing_module.prefixed_id

    def forced_source_id(prefix, *parts):
        if prefix == "src":
            return "src_forced_collision"
        return real_prefixed_id(prefix, *parts)

    monkeypatch.setattr(importing_module, "prefixed_id", forced_source_id)
    package = {
        "entities": [{"entity_type": "COMPANY", "canonical_name": "Acme"}],
        "sources": [
            _source(ref="collision", title="First report"),
            _source(ref="collision", title="Unrelated report"),
        ],
        "observations": [
            {
                "source_ref": "collision",
                "observation_type": "PRODUCT_LAUNCH",
                "subject": "Acme",
            }
        ],
    }

    snapshot = import_package(package, created_at=CREATED_AT)
    codes = {error["error_code"] for error in snapshot.import_errors}

    assert "SOURCE_CONTENT_HASH_COLLISION" in codes
    assert snapshot.observations == []

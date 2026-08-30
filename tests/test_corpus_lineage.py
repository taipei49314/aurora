"""Digest-bound real-corpus lineage and deterministic import timestamps."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from adapters import convert_patentsview, strip_package
from adapters.corpus_lineage import (
    SCHEMA_VERSION,
    corpus_manifest_sha256,
    load_corpus_lineage,
)
from aurora import import_package
from scripts.check_case_scorecard import main as scorecard_main


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "cases" / "patentsview-sample"


@pytest.mark.unit
def test_real_patentsview_manifest_binds_vendored_dump():
    lineage = load_corpus_lineage(
        CASE / "corpus-manifest.json", CASE / "dump.json"
    )
    manifest = json.loads(
        (CASE / "corpus-manifest.json").read_text(encoding="utf-8")
    )
    dump = json.loads((CASE / "dump.json").read_text(encoding="utf-8"))
    assert lineage["schema_version"] == SCHEMA_VERSION
    assert lineage["dataset_version"] == "2024-12-31"
    assert lineage["license"] == "CC-BY-4.0"
    assert lineage["manifest_sha256"] == corpus_manifest_sha256(manifest)
    assert dump["_provenance"]["status"] == "official-real-data-snapshot"
    assert [row["patent_id"] for row in dump["patents"]] == manifest["selection"][
        "record_ids"
    ]


@pytest.mark.unit
def test_manifest_rejects_tampered_artifact(tmp_path):
    manifest = tmp_path / "corpus-manifest.json"
    dump = tmp_path / "dump.json"
    shutil.copyfile(CASE / "corpus-manifest.json", manifest)
    shutil.copyfile(CASE / "dump.json", dump)
    dump.write_bytes(dump.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="byte count mismatch"):
        load_corpus_lineage(manifest, dump)


@pytest.mark.unit
def test_manifest_root_must_be_object(tmp_path):
    manifest = tmp_path / "corpus-manifest.json"
    dump = tmp_path / "dump.json"
    manifest.write_text("[]\n", encoding="utf-8")
    dump.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be an object"):
        load_corpus_lineage(manifest, dump)


@pytest.mark.unit
def test_manifest_rejects_non_string_identity_and_boolean_bytes(tmp_path):
    source_manifest = json.loads(
        (CASE / "corpus-manifest.json").read_text(encoding="utf-8")
    )
    dump = tmp_path / "dump.json"
    shutil.copyfile(CASE / "dump.json", dump)
    manifest = tmp_path / "corpus-manifest.json"

    source_manifest["dataset"]["id"] = {"not": "a string"}
    manifest.write_text(json.dumps(source_manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="dataset.id must be a string"):
        load_corpus_lineage(manifest, dump)

    source_manifest["dataset"]["id"] = "valid"
    source_manifest["artifacts"][0]["bytes"] = False
    manifest.write_text(json.dumps(source_manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid byte count"):
        load_corpus_lineage(manifest, dump)


@pytest.mark.integration
def test_lineage_survives_strip_and_stabilizes_import_timestamp():
    lineage = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": "example",
        "dataset_version": "2024-01-01",
        "retrieved_at": "2024-02-03T04:05:06+00:00",
        "origin_url": "https://example.test/data",
        "license": "CC-BY-4.0",
        "manifest_sha256": "sha256:" + "a" * 64,
    }
    package = convert_patentsview({"patents": [{
        "patent_id": "123",
        "patent_title": "Lineaged patent",
        "patent_date": "2024-01-02",
        "assignees": [{"assignee_organization": "Acme"}],
    }]}, lineage=lineage)
    clean = strip_package(package)
    assert clean["lineage"] == lineage
    snapshot = import_package(clean)
    assert snapshot.created_at == lineage["retrieved_at"]
    assert {source.retrieved_at for source in snapshot.sources} == {
        lineage["retrieved_at"]
    }
    assert snapshot.input_manifest_hash() == import_package(clean).input_manifest_hash()


@pytest.mark.integration
def test_merged_lineage_uses_latest_acquisition_time():
    snapshot = import_package({
        "entities": [],
        "sources": [],
        "observations": [],
        "lineage": {
            "schema_version": "aurora-package-lineage/v1",
            "datasets": [
                {"retrieved_at": "2024-02-01T00:00:00+00:00"},
                {"retrieved_at": "2024-03-01T00:00:00+00:00"},
            ],
        },
    })
    assert snapshot.created_at == "2024-03-01T00:00:00+00:00"


@pytest.mark.integration
def test_invalid_source_retrieval_time_fails_closed():
    snapshot = import_package({
        "entities": [],
        "sources": [{
            "ref": "s1",
            "source_type": "PATENT",
            "publisher": "USPTO",
            "title": "Bad retrieval time",
            "retrieved_at": "not-a-time",
            "metadata": {"retrieved_at": "2099-01-01T00:00:00+00:00"},
        }],
        "observations": [],
    }, created_at="2024-01-01T00:00:00+00:00")
    assert snapshot.sources[0].retrieved_at == "2024-01-01T00:00:00+00:00"
    assert "retrieved_at" not in snapshot.sources[0].metadata
    assert any(
        error.get("error_code") == "SOURCE_RETRIEVED_AT_INVALID"
        for error in snapshot.import_errors
    )


@pytest.mark.integration
@pytest.mark.parametrize("retrieved_at", ["2024-02-01", "2024-02-01T12:00:00"])
def test_source_retrieval_time_requires_timezone(retrieved_at):
    snapshot = import_package({
        "entities": [],
        "sources": [{
            "ref": "s1",
            "source_type": "PATENT",
            "publisher": "USPTO",
            "title": "Naive retrieval time",
            "retrieved_at": retrieved_at,
        }],
        "observations": [],
    }, created_at="2024-01-01T00:00:00+00:00")
    assert snapshot.sources[0].retrieved_at == "2024-01-01T00:00:00+00:00"
    assert any(
        error.get("error_code") == "SOURCE_RETRIEVED_AT_INVALID"
        for error in snapshot.import_errors
    )


@pytest.mark.integration
def test_committed_patentsview_package_is_bound_to_dump(tmp_path):
    package = json.loads((CASE / "package.json").read_text(encoding="utf-8"))
    dump = json.loads((CASE / "dump.json").read_text(encoding="utf-8"))
    lineage = load_corpus_lineage(
        CASE / "corpus-manifest.json", CASE / "dump.json"
    )
    assert package == strip_package(convert_patentsview(dump, lineage=lineage))
    assert package["lineage"] == lineage
    for collection in ("entities", "sources", "observations", "documents"):
        assert package[collection]
        assert all(
            (row.get("metadata") or {}).get("corpus_lineage") == lineage
            for row in package[collection]
        )

    tampered_case = tmp_path / "patentsview-sample"
    tampered_case.mkdir()
    for name in ("dump.json", "corpus-manifest.json"):
        shutil.copyfile(CASE / name, tampered_case / name)
    scorecard = json.loads(
        (CASE / "scorecard.json").read_text(encoding="utf-8")
    )
    scorecard["dump"] = "dump.json"
    (tampered_case / "scorecard.json").write_text(
        json.dumps(scorecard), encoding="utf-8"
    )
    package["entities"][0]["canonical_name"] += " (tampered)"
    (tampered_case / "package.json").write_text(
        json.dumps(package), encoding="utf-8"
    )
    assert scorecard_main([str(tampered_case)]) == 1

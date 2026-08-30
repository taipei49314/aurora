"""Validate and compact an offline corpus lineage manifest.

The manifest keeps artifact-level SHA-256 provenance separate from AURORA's
row-level ``Source.content_hash``.  Adapters can stamp the compact digest into
their package rows without copying a large acquisition manifest everywhere.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


SCHEMA_VERSION = "aurora-corpus-lineage/v1"
_SHA256_RE = re.compile(r"^(?:sha256:)?([0-9a-fA-F]{64})$")


def canonical_manifest_bytes(manifest: dict) -> bytes:
    """Return the stable JSON representation used for the manifest digest."""
    if not isinstance(manifest, dict):
        raise ValueError("corpus manifest must be an object")
    return json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def corpus_manifest_sha256(manifest: dict) -> str:
    """Return a namespaced SHA-256 of the canonical manifest object."""
    digest = hashlib.sha256(canonical_manifest_bytes(manifest)).hexdigest()
    return f"sha256:{digest}"


def file_sha256(path: Path) -> str:
    """Hash a file in bounded memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"corpus manifest {field} must be a string")
    text = value.strip()
    if not text:
        raise ValueError(f"corpus manifest missing {field}")
    return text


def load_corpus_lineage(manifest_path: Path, artifact_path: Path) -> Dict[str, Any]:
    """Validate *manifest_path* and *artifact_path*, then return compact lineage.

    Artifact paths in the manifest are relative POSIX paths.  They may not leave
    the manifest directory.  The checked byte count and SHA-256 make stale or
    locally edited vendored data fail closed.
    """
    manifest_path = Path(manifest_path).resolve()
    artifact_path = Path(artifact_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("corpus manifest must be an object")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported corpus manifest schema: {manifest.get('schema_version')!r}"
        )

    dataset = manifest.get("dataset")
    retrieval = manifest.get("retrieval")
    if not isinstance(dataset, dict):
        raise ValueError("corpus manifest missing dataset object")
    if not isinstance(retrieval, dict):
        raise ValueError("corpus manifest missing retrieval object")

    dataset_id = _required_text(dataset.get("id"), "dataset.id")
    dataset_version = _required_text(dataset.get("version"), "dataset.version")
    origin_url = _required_text(dataset.get("origin_url"), "dataset.origin_url")
    license_s = _required_text(dataset.get("license"), "dataset.license")
    retrieved_at = _required_text(
        retrieval.get("retrieved_at"), "retrieval.retrieved_at"
    )
    try:
        parsed_retrieval = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("corpus manifest retrieval.retrieved_at must be ISO-8601") from exc
    if parsed_retrieval.tzinfo is None:
        raise ValueError(
            "corpus manifest retrieval.retrieved_at must include a timezone"
        )

    try:
        artifact_rel = artifact_path.relative_to(manifest_path.parent).as_posix()
    except ValueError as exc:
        raise ValueError("corpus artifact must be inside the manifest directory") from exc
    if artifact_rel.startswith("../") or Path(artifact_rel).is_absolute():
        raise ValueError("unsafe corpus artifact path")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("corpus manifest missing artifacts array")
    matches = [
        row
        for row in artifacts
        if isinstance(row, dict) and str(row.get("path") or "") == artifact_rel
    ]
    if len(matches) != 1:
        raise ValueError(f"corpus manifest must describe artifact {artifact_rel!r} once")
    artifact = matches[0]
    match = _SHA256_RE.fullmatch(str(artifact.get("sha256") or ""))
    if match is None:
        raise ValueError(f"invalid SHA-256 for corpus artifact {artifact_rel!r}")
    expected_hash = match.group(1).lower()
    expected_bytes = artifact.get("bytes")
    if type(expected_bytes) is not int or expected_bytes < 0:
        raise ValueError(f"invalid byte count for corpus artifact {artifact_rel!r}")
    actual_bytes = artifact_path.stat().st_size
    if actual_bytes != expected_bytes:
        raise ValueError(
            f"corpus artifact byte count mismatch for {artifact_rel!r}: "
            f"expected {expected_bytes}, got {actual_bytes}"
        )
    actual_hash = file_sha256(artifact_path)
    if actual_hash != expected_hash:
        raise ValueError(
            f"corpus artifact SHA-256 mismatch for {artifact_rel!r}: "
            f"expected {expected_hash}, got {actual_hash}"
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "retrieved_at": retrieved_at,
        "origin_url": origin_url,
        "license": license_s,
        "artifact_path": artifact_rel,
        "artifact_bytes": expected_bytes,
        "artifact_sha256": f"sha256:{expected_hash}",
        "manifest_sha256": corpus_manifest_sha256(manifest),
    }

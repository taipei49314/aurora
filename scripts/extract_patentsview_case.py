#!/usr/bin/env python3
"""Rebuild the small real-data PatentsView case from the official 2024 archive.

The upstream ZIP files are intentionally not committed.  Download the three
named artifacts from the URLs below, then point ``--input-dir`` at them.  This
script verifies official byte counts and MD5 checksums before extracting five
commit-pinned PatentsView documentation/validation record IDs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = ROOT / ".tmp" / "patentsview-2024"
DEFAULT_CASE_DIR = ROOT / "cases" / "patentsview-sample"
RETRIEVED_AT = "2026-08-30T14:12:16+08:00"
ZENODO_RECORD = "15058362"
ZENODO_DOI = "10.5281/zenodo.15058362"
ORIGIN_URL = f"https://doi.org/{ZENODO_DOI}"
DATASET_VERSION = "2024-12-31"
PATENTSEARCH_COMMIT = "9dd76bf92168a84a6a5e9be429e7df575ce99c5e"
SELECTED_IDS = (
    "10905426",
    "11172927",
    "D345393",
    "10849265",
    "10849287",
)
UPSTREAM = (
    {
        "name": "g_patent.tsv.zip",
        "member": "g_patent.tsv",
        "bytes": 223192856,
        "md5": "f74fbde4b2adbf980b8e4ed5394f16d2",
        "record_key": "patent_id",
    },
    {
        "name": "g_application.tsv.zip",
        "member": "g_application.tsv",
        "bytes": 68669855,
        "md5": "26001068098f4240e0762c63ffbb331e",
        "record_key": "patent_id",
    },
    {
        "name": "g_assignee_not_disambiguated.tsv.zip",
        "member": "g_assignee_not_disambiguated.tsv",
        "bytes": 476589877,
        "md5": "6154c6d989206de65b1367b886f744d3",
        "record_key": "patent_id",
    },
)


def _hash_file(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_upstream(input_dir: Path, spec: dict) -> Path:
    path = input_dir / spec["name"]
    if not path.is_file():
        raise FileNotFoundError(f"missing upstream artifact: {path}")
    if path.stat().st_size != spec["bytes"]:
        raise ValueError(
            f"byte count mismatch for {path.name}: "
            f"expected {spec['bytes']}, got {path.stat().st_size}"
        )
    actual = _hash_file(path, "md5")
    if actual != spec["md5"]:
        raise ValueError(
            f"MD5 mismatch for {path.name}: expected {spec['md5']}, got {actual}"
        )
    return path


def _selected_rows(path: Path, member: str, record_key: str) -> Dict[str, List[dict]]:
    selected = set(SELECTED_IDS)
    rows: Dict[str, List[dict]] = {patent_id: [] for patent_id in SELECTED_IDS}
    with zipfile.ZipFile(path) as archive, archive.open(member) as binary:
        text = io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")
        for row in csv.DictReader(text, delimiter="\t"):
            patent_id = str(row.get(record_key) or "").strip()
            if patent_id in selected:
                rows[patent_id].append(
                    {str(key): str(value or "").strip() for key, value in row.items()}
                )
    missing = [patent_id for patent_id, found in rows.items() if not found]
    if missing:
        raise ValueError(f"missing selected {member} rows: {', '.join(missing)}")
    return rows


def _as_int(value: str) -> int:
    return int(str(value).strip())


def _as_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _patent_record(patent: dict, application: dict, assignees: Iterable[dict]) -> dict:
    return {
        "patent_id": patent["patent_id"],
        "patent_type": patent["patent_type"],
        "patent_date": patent["patent_date"],
        "patent_title": patent["patent_title"],
        "wipo_kind": patent["wipo_kind"],
        "num_claims": _as_int(patent["num_claims"]),
        "withdrawn": _as_bool(patent["withdrawn"]),
        "application": {
            "application_id": application["application_id"],
            "patent_application_type": application["patent_application_type"],
            "filing_date": application["filing_date"],
            "series_code": application["series_code"],
            "rule_47_flag": _as_bool(application["rule_47_flag"]),
        },
        "assignees": [
            {
                "assignee_sequence": _as_int(row["assignee_sequence"]),
                "assignee_id": row["assignee_id"],
                "raw_assignee_individual_name_first": row[
                    "raw_assignee_individual_name_first"
                ],
                "raw_assignee_individual_name_last": row[
                    "raw_assignee_individual_name_last"
                ],
                "raw_assignee_organization": row["raw_assignee_organization"],
                "assignee_type": _as_int(row["assignee_type"]),
                "rawlocation_id": row["rawlocation_id"],
            }
            for row in sorted(assignees, key=lambda row: _as_int(row["assignee_sequence"]))
        ],
    }


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def build_case(input_dir: Path, case_dir: Path) -> None:
    paths = {spec["name"]: _verify_upstream(input_dir, spec) for spec in UPSTREAM}
    patent_rows = _selected_rows(
        paths["g_patent.tsv.zip"], "g_patent.tsv", "patent_id"
    )
    application_rows = _selected_rows(
        paths["g_application.tsv.zip"], "g_application.tsv", "patent_id"
    )
    assignee_rows = _selected_rows(
        paths["g_assignee_not_disambiguated.tsv.zip"],
        "g_assignee_not_disambiguated.tsv",
        "patent_id",
    )

    for patent_id in SELECTED_IDS:
        if len(patent_rows[patent_id]) != 1:
            raise ValueError(f"expected one patent row for {patent_id}")
        if len(application_rows[patent_id]) != 1:
            raise ValueError(f"expected one application row for {patent_id}")

    dump = {
        "_provenance": {
            "status": "official-real-data-snapshot",
            "dataset_id": "uspto-patentsview-granted-metadata",
            "dataset_version": DATASET_VERSION,
            "source_owner": "United States Patent and Trademark Office",
            "source_url": ORIGIN_URL,
            "retrieved_at": RETRIEVED_AT,
            "license": "CC-BY-4.0",
            "official_record": False,
            "changes_made": True,
            "record_ids": list(SELECTED_IDS),
        },
        "count": len(SELECTED_IDS),
        "patents": [
            _patent_record(
                patent_rows[patent_id][0],
                application_rows[patent_id][0],
                assignee_rows[patent_id],
            )
            for patent_id in SELECTED_IDS
        ],
    }
    dump_bytes = _json_bytes(dump)
    dump_hash = hashlib.sha256(dump_bytes).hexdigest()

    manifest = {
        "schema_version": "aurora-corpus-lineage/v1",
        "dataset": {
            "id": "uspto-patentsview-granted-metadata",
            "title": "Final release of PatentsView metadata, granted patents",
            "owner": "United States Patent and Trademark Office",
            "version": DATASET_VERSION,
            "publication_date": "2025-03-20",
            "doi": ZENODO_DOI,
            "origin_url": ORIGIN_URL,
            "license": "CC-BY-4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "official_record": False,
        },
        "retrieval": {
            "retrieved_at": RETRIEVED_AT,
            "method": "official Zenodo archive download",
        },
        "selection": {
            "record_key": "patent_id",
            "record_ids": list(SELECTED_IDS),
            "rule": (
                "Three records from the commit-pinned PatentSearch API example "
                "and two from its commit-pinned validation data."
            ),
            "sources": [
                {
                    "record_ids": ["10905426", "11172927", "D345393"],
                    "url": (
                        "https://github.com/PatentsView/PatentSearch-API/blob/"
                        f"{PATENTSEARCH_COMMIT}/docs/docs/Search%20API/Examples.md"
                    ),
                },
                {
                    "record_ids": ["10849265", "10849287"],
                    "url": (
                        "https://github.com/PatentsView/PatentSearch-API/blob/"
                        f"{PATENTSEARCH_COMMIT}/API/testing_validation/"
                        "patent_citations/test_and_simple.json"
                    ),
                },
            ],
        },
        "upstream_artifacts": [
            {
                "name": spec["name"],
                "url": (
                    f"https://zenodo.org/api/records/{ZENODO_RECORD}/files/"
                    f"{spec['name']}/content"
                ),
                "bytes": spec["bytes"],
                "checksum": f"md5:{spec['md5']}",
            }
            for spec in UPSTREAM
        ],
        "transform": {
            "script": "scripts/extract_patentsview_case.py",
            "version": "1",
            "description": (
                "Verify official archives, join patent/application/assignee rows "
                "by patent_id, trim surrounding whitespace, and serialize a "
                "PatentsView-compatible JSON snapshot. No evidence fields are synthesized."
            ),
            "changes_made": True,
        },
        "artifacts": [
            {
                "path": "dump.json",
                "bytes": len(dump_bytes),
                "sha256": dump_hash,
            }
        ],
        "attribution": (
            "Contains PatentsView patent data from the U.S. Patent and Trademark "
            "Office, retrieved from the cited archive and licensed under CC BY 4.0. "
            "Transformed to the Aurora fixture schema; changes made. PatentsView "
            "research data do not constitute the official USPTO record."
        ),
    }

    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "dump.json").write_bytes(dump_bytes)
    (case_dir / "corpus-manifest.json").write_bytes(_json_bytes(manifest))
    print(
        f"wrote {case_dir / 'dump.json'} ({len(dump_bytes)} bytes, sha256:{dump_hash})"
    )
    print(f"wrote {case_dir / 'corpus-manifest.json'}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--case-dir", type=Path, default=DEFAULT_CASE_DIR)
    args = parser.parse_args(argv)
    try:
        build_case(args.input_dir.resolve(), args.case_dir.resolve())
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

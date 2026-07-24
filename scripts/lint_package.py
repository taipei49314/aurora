#!/usr/bin/env python3
"""Lint an AURORA import package (structure + engine import + quick stats).

  PYTHONPATH=backend python scripts/lint_package.py examples/real_mini_package.json
  PYTHONPATH=backend python scripts/lint_package.py cases/multisource-iron-air/package.json --json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _obs_document_id(row: dict) -> str:
    did = (row.get("document_id") or "").strip()
    if did:
        return did
    meta = row.get("metadata") or {}
    if isinstance(meta, dict):
        return (meta.get("document_id") or "").strip()
    return ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("package", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="Fail on any import_errors")
    ap.add_argument(
        "--require-license",
        action="store_true",
        help="Fail if any source lacks a first-class license (public-corpus policy)",
    )
    ap.add_argument(
        "--public-corpus",
        action="store_true",
        help="Alias for --require-license (sources must declare redistribution license)",
    )
    ap.add_argument(
        "--require-documents",
        action="store_true",
        help=(
            "Fail if any observation.document_id has no matching documents[] row "
            "(span/provenance policy; engine 0.1.22+)"
        ),
    )
    ap.add_argument(
        "--require-char-spans",
        action="store_true",
        help=(
            "Fail if any observation with document_id lacks char_span after import "
            "(engine auto-align counts; 0.1.26+)"
        ),
    )
    ap.add_argument(
        "--min-char-span-ratio",
        type=float,
        default=None,
        metavar="R",
        help=(
            "Fail if observations_with_char_span / observations < R "
            "(0..1; post-import, includes auto-align; 0.1.26+)"
        ),
    )
    ap.add_argument(
        "--no-provisional",
        action="store_true",
        help=(
            "Fail if any provisional entity remains after import "
            "(type PROVISIONAL or metadata.provisional; engine 0.1.40+)"
        ),
    )
    ap.add_argument(
        "--forbid-provisional",
        action="store_true",
        help="Alias for --no-provisional",
    )
    args = ap.parse_args(argv)
    forbid_provisional = args.no_provisional or args.forbid_provisional
    require_license = args.require_license or args.public_corpus
    if args.min_char_span_ratio is not None:
        if not (0.0 <= args.min_char_span_ratio <= 1.0):
            ap.error("--min-char-span-ratio must be between 0 and 1")

    sys.path.insert(0, str(ROOT / "backend"))
    from aurora import import_package
    from aurora.models import SOURCE_TYPES, ENTITY_TYPES, OBSERVATION_TYPES

    raw = json.loads(args.package.read_text(encoding="utf-8"))
    report = {
        "path": str(args.package),
        "ok": True,
        "issues": [],
        "counts": {},
        "source_types": {},
        "observation_types": {},
        "entity_types": {},
        "entities_with_external_ids": 0,
        "sources_with_license": 0,
        "license_counts": {},
        "import_errors": 0,
        "documents_total": 0,
        "documents_with_text": 0,
        "document_ids_referenced": 0,
        "observations_with_document_id": 0,
        "observations_with_char_span": 0,
        "observations_missing_char_span": 0,
        "char_span_ratio": 0.0,
        "orphan_document_ids": [],
        "orphan_document_id_count": 0,
        "provisional_entities": 0,
        "provisional_entity_names": [],
    }

    for key in ("entities", "sources", "observations"):
        if key not in raw or not isinstance(raw.get(key), list):
            report["issues"].append(f"missing or non-array top-level key: {key}")
            report["ok"] = False

    if not report["ok"]:
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            for i in report["issues"]:
                print(f"FAIL {i}")
        return 1

    # vocab lint (soft → hard when unknown)
    for i, e in enumerate(raw.get("entities") or []):
        et = e.get("entity_type")
        if et and et not in ENTITY_TYPES:
            report["issues"].append(f"entities[{i}] unknown entity_type {et}")
    for i, s in enumerate(raw.get("sources") or []):
        st = s.get("source_type")
        if st and st not in SOURCE_TYPES:
            report["issues"].append(f"sources[{i}] unknown source_type {st}")
    for i, o in enumerate(raw.get("observations") or []):
        ot = o.get("observation_type")
        if ot and ot not in OBSERVATION_TYPES:
            report["issues"].append(f"observations[{i}] unknown observation_type {ot}")

    # Document provenance pre-check (raw package, before import)
    docs_raw = raw.get("documents") or []
    if docs_raw and not isinstance(docs_raw, list):
        report["issues"].append("documents must be an array when present")
        report["ok"] = False
        docs_raw = []

    doc_ids_present = set()
    docs_with_text = 0
    for d in docs_raw:
        if not isinstance(d, dict):
            continue
        did = (d.get("document_id") or d.get("id") or "").strip()
        if did:
            doc_ids_present.add(did)
        if (d.get("text") or d.get("body") or "").strip():
            docs_with_text += 1

    referenced: set = set()
    obs_with_doc = 0
    obs_with_span = 0
    for o in raw.get("observations") or []:
        if not isinstance(o, dict):
            continue
        did = _obs_document_id(o)
        if did:
            referenced.add(did)
            obs_with_doc += 1
        span = o.get("char_span")
        if span is None and isinstance(o.get("metadata"), dict):
            span = o["metadata"].get("char_span")
        if span not in (None, ""):
            obs_with_span += 1

    orphan_ids = sorted(referenced - doc_ids_present)
    report["documents_total"] = len(doc_ids_present)
    report["documents_with_text"] = docs_with_text
    report["document_ids_referenced"] = len(referenced)
    report["observations_with_document_id"] = obs_with_doc
    report["observations_with_char_span"] = obs_with_span
    report["orphan_document_ids"] = orphan_ids
    report["orphan_document_id_count"] = len(orphan_ids)

    # Preserve package-level license default for import; include documents[]
    # and provisional staging flags (0.1.39+) so lint sees staged entities.
    pkg = {
        "entities": raw.get("entities") or [],
        "sources": raw.get("sources") or [],
        "observations": raw.get("observations") or [],
    }
    if docs_raw:
        pkg["documents"] = list(docs_raw)
    if raw.get("license"):
        pkg["license"] = raw["license"]
    elif isinstance(raw.get("package"), dict) and raw["package"].get("license"):
        pkg["package"] = {"license": raw["package"]["license"]}
    elif isinstance(raw.get("meta"), dict) and raw["meta"].get("license"):
        pkg["meta"] = {"license": raw["meta"]["license"]}
    for flag in ("stage_unresolved", "stage_unresolved_subjects", "provisional_entity_type"):
        if flag in raw:
            pkg[flag] = raw[flag]
    if isinstance(raw.get("package"), dict):
        pkg_pkg = dict(pkg.get("package") or {})
        for flag in ("stage_unresolved", "provisional_entity_type", "license"):
            if flag in raw["package"] and flag not in pkg_pkg:
                pkg_pkg[flag] = raw["package"][flag]
        if pkg_pkg:
            pkg["package"] = pkg_pkg

    snap = import_package(pkg)
    report["import_errors"] = len(snap.import_errors or [])
    report["counts"] = dict(snap.counts)
    report["source_types"] = dict(Counter(s.source_type for s in snap.sources))
    report["observation_types"] = dict(
        Counter(o.observation_type for o in snap.observations)
    )
    report["entity_types"] = dict(Counter(e.entity_type for e in snap.entities))
    report["entities_with_external_ids"] = sum(
        1 for e in snap.entities if e.external_ids
    )
    # Prefer post-import document counts when import succeeded
    snap_docs = getattr(snap, "documents", None) or []
    if snap_docs:
        report["documents_total"] = len(snap_docs)
        report["documents_with_text"] = sum(
            1 for d in snap_docs if (getattr(d, "text", None) or "").strip()
        )
    # Post-import span count (includes auto-aligned)
    n_obs = len(snap.observations)
    n_spans = sum(
        1 for o in snap.observations if getattr(o, "char_span", None) is not None
    )
    n_with_doc = sum(
        1 for o in snap.observations if (getattr(o, "document_id", None) or "").strip()
    )
    missing_span_with_doc = sum(
        1
        for o in snap.observations
        if (getattr(o, "document_id", None) or "").strip()
        and getattr(o, "char_span", None) is None
    )
    report["observations_with_char_span"] = n_spans
    report["observations_with_document_id"] = n_with_doc
    report["observations_missing_char_span"] = missing_span_with_doc
    report["char_span_ratio"] = (n_spans / n_obs) if n_obs else 0.0
    report["char_spans_auto_aligned"] = int(
        (snap.counts or {}).get("char_spans_auto_aligned") or 0
    )

    license_counter: Counter = Counter()
    missing_license = 0
    for s in snap.sources:
        lic = (getattr(s, "license", None) or "").strip()
        if lic:
            license_counter[lic] += 1
        else:
            missing_license += 1
    report["sources_with_license"] = sum(license_counter.values())
    report["license_counts"] = dict(license_counter)
    report["sources_missing_license"] = missing_license

    # Provisional entities (soft stats always; hard with --no-provisional, 0.1.40+)
    provisional = [
        e
        for e in snap.entities
        if e.entity_type == "PROVISIONAL" or (e.metadata or {}).get("provisional")
    ]
    report["provisional_entities"] = len(provisional)
    report["provisional_entity_names"] = sorted(
        {e.canonical_name for e in provisional if e.canonical_name}
    )
    report["entities_provisional"] = len(provisional)

    if require_license and missing_license:
        report["ok"] = False
        report["issues"].append(
            f"{missing_license} source(s) missing license "
            f"(public-corpus policy: every source needs Source.license)"
        )
    if args.require_documents and orphan_ids:
        report["ok"] = False
        sample = ", ".join(orphan_ids[:8])
        more = f" (+{len(orphan_ids) - 8} more)" if len(orphan_ids) > 8 else ""
        report["issues"].append(
            f"{len(orphan_ids)} observation document_id(s) have no documents[] row: "
            f"{sample}{more} "
            f"(use ensure_documents / --require-documents policy)"
        )
    if args.require_char_spans and missing_span_with_doc:
        report["ok"] = False
        report["issues"].append(
            f"{missing_span_with_doc} observation(s) with document_id lack char_span "
            f"(post-import; try progressive align / append_unmatched / "
            f"--require-char-spans policy)"
        )
    if args.min_char_span_ratio is not None:
        ratio = report["char_span_ratio"]
        if ratio + 1e-12 < float(args.min_char_span_ratio):
            report["ok"] = False
            report["issues"].append(
                f"char_span_ratio={ratio:.3f} < min-char-span-ratio "
                f"{args.min_char_span_ratio} "
                f"({n_spans}/{n_obs} observations)"
            )
    if forbid_provisional and provisional:
        report["ok"] = False
        sample = ", ".join(report["provisional_entity_names"][:8])
        more = (
            f" (+{len(report['provisional_entity_names']) - 8} more)"
            if len(report["provisional_entity_names"]) > 8
            else ""
        )
        report["issues"].append(
            f"{len(provisional)} provisional entit(y/ies) present: {sample}{more} "
            f"(promote via resolve_entities --promote or remove stage_unresolved; "
            f"--no-provisional policy)"
        )
    if args.strict and report["import_errors"]:
        report["ok"] = False
        report["issues"].append(f"{report['import_errors']} import_errors")
    if report["issues"] and any("unknown" in i for i in report["issues"]):
        report["ok"] = False

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"package: {args.package}")
        print(f"  counts: {report['counts']}")
        print(f"  source_types: {report['source_types']}")
        print(f"  observation_types: {report['observation_types']}")
        print(
            f"  entities_with_external_ids: {report['entities_with_external_ids']}/"
            f"{report['counts'].get('entities', 0)}"
        )
        print(
            f"  provisional_entities: {report['provisional_entities']}"
            + (
                f"  names={report['provisional_entity_names'][:5]}"
                if report["provisional_entities"]
                else ""
            )
        )
        print(
            f"  sources_with_license: {report['sources_with_license']}/"
            f"{report['counts'].get('sources', 0)}"
            f"  licenses={report['license_counts']}"
        )
        print(
            f"  documents: {report['documents_total']} "
            f"({report['documents_with_text']} with text) · "
            f"referenced={report['document_ids_referenced']} · "
            f"orphan_ids={report['orphan_document_id_count']} · "
            f"obs_with_doc={report['observations_with_document_id']} · "
            f"spans={report['observations_with_char_span']}/{n_obs} "
            f"({report['char_span_ratio']:.0%}) "
            f"missing_on_doc={report['observations_missing_char_span']} "
            f"auto={report.get('char_spans_auto_aligned', 0)}"
        )
        print(f"  import_errors: {report['import_errors']}")
        for i in report["issues"][:20]:
            print(f"  ISSUE: {i}")
        print("OK" if report["ok"] else "FAIL")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

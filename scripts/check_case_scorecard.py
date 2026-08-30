#!/usr/bin/env python3
"""Check a case package against its scorecard.json gates."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "case_dir",
        type=Path,
        nargs="?",
        default=ROOT / "cases" / "iron-air-mini",
    )
    args = p.parse_args(argv)
    case_dir = args.case_dir
    scorecard = json.loads((case_dir / "scorecard.json").read_text(encoding="utf-8"))
    package = json.loads((case_dir / "package.json").read_text(encoding="utf-8"))
    gates = scorecard["gates"]
    preflight_failures = []
    lineage = None

    manifest_name = scorecard.get("corpus_manifest")
    if gates.get("require_corpus_lineage") and not manifest_name:
        preflight_failures.append("require_corpus_lineage needs corpus_manifest")
    if manifest_name:
        sys.path.insert(0, str(ROOT))
        from adapters.corpus_lineage import load_corpus_lineage

        dump_value = Path(scorecard.get("dump") or "dump.json")
        dump_path = dump_value if dump_value.is_absolute() else ROOT / dump_value
        if not dump_path.is_file():
            dump_path = case_dir / dump_value.name
        try:
            lineage = load_corpus_lineage(case_dir / manifest_name, dump_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            preflight_failures.append(f"corpus lineage validation failed: {exc}")
        else:
            if package.get("lineage") != lineage:
                preflight_failures.append(
                    "package lineage does not match corpus manifest digest"
                )
            for collection in ("entities", "sources", "observations", "documents"):
                mismatched = [
                    index
                    for index, row in enumerate(package.get(collection) or [])
                    if not isinstance(row, dict)
                    or (row.get("metadata") or {}).get("corpus_lineage") != lineage
                ]
                if mismatched:
                    preflight_failures.append(
                        f"{collection} rows missing corpus lineage: {mismatched[:5]}"
                    )
            dump = json.loads(dump_path.read_text(encoding="utf-8"))
            status = str((dump.get("_provenance") or {}).get("status") or "")
            required_status = gates.get("require_provenance_status")
            if required_status and status != required_status:
                preflight_failures.append(
                    f"provenance status {status!r} != required {required_status!r}"
                )
            if "synthetic" in status.lower() or "fixture" in status.lower():
                preflight_failures.append(
                    f"real corpus gate rejects provenance status {status!r}"
                )
            manifest = json.loads(
                (case_dir / manifest_name).read_text(encoding="utf-8")
            )
            expected_ids = (manifest.get("selection") or {}).get("record_ids") or []
            actual_ids = [str(row.get("patent_id")) for row in dump.get("patents") or []]
            if actual_ids != expected_ids:
                preflight_failures.append(
                    "dump patent IDs/order do not match corpus manifest selection"
                )
            if gates.get("require_generated_package_match"):
                if scorecard.get("adapters") != ["patentsview"]:
                    preflight_failures.append(
                        "generated package comparison is unsupported for these adapters"
                    )
                else:
                    from adapters import convert_patentsview, strip_package

                    regenerated = strip_package(
                        convert_patentsview(dump, lineage=lineage)
                    )
                    if package != regenerated:
                        preflight_failures.append(
                            "package does not match deterministic dump conversion"
                        )

    sys.path.insert(0, str(ROOT / "backend"))
    from aurora import import_package

    # Preserve staging flags so provisional entities from stage_unresolved are visible (0.1.41+)
    pkg = {
        "entities": package.get("entities", []),
        "sources": package.get("sources", []),
        "observations": package.get("observations", []),
    }
    if package.get("documents"):
        pkg["documents"] = package["documents"]
    for flag in (
        "license",
        "lineage",
        "stage_unresolved",
        "stage_unresolved_subjects",
        "provisional_entity_type",
    ):
        if flag in package:
            pkg[flag] = package[flag]
    if isinstance(package.get("package"), dict):
        pkg["package"] = dict(package["package"])
    snap = import_package(pkg)
    n_err = len(snap.import_errors or [])
    obs_types = {o.observation_type for o in snap.observations}
    raw = snap.counts.get("raw_source_count", 0)
    indep = snap.counts.get("independent_source_count", 0)
    n_docs = len(getattr(snap, "documents", None) or [])
    n_obs = len(snap.observations)
    n_spans = sum(
        1 for o in snap.observations if getattr(o, "char_span", None) is not None
    )
    span_ratio = (n_spans / n_obs) if n_obs else 0.0
    provisional = [
        e
        for e in snap.entities
        if e.entity_type == "PROVISIONAL" or (e.metadata or {}).get("provisional")
    ]
    n_provisional = len(provisional)

    # Orphan document_ids: referenced by obs but missing from documents[]
    present = {
        (d.document_id if hasattr(d, "document_id") else d.get("document_id", "")).strip()
        for d in (getattr(snap, "documents", None) or [])
    }
    referenced = set()
    for o in snap.observations:
        did = (getattr(o, "document_id", None) or "").strip()
        if did:
            referenced.add(did)
    orphans = sorted(referenced - present)

    failures = list(preflight_failures)
    if n_err > gates.get("import_errors_max", 0):
        failures.append(f"import_errors={n_err} > max {gates['import_errors_max']}")
    for t in gates.get("require_observation_types", []):
        if t not in obs_types:
            failures.append(f"missing observation_type {t}")
    if gates.get("independent_lt_raw") and not (indep < raw):
        failures.append(f"expected independent ({indep}) < raw ({raw})")
    if gates.get("independent_eq_raw") and indep != raw:
        failures.append(f"expected independent ({indep}) == raw ({raw})")
    if raw < gates.get("min_sources", 0):
        failures.append(f"raw sources {raw} < min_sources {gates['min_sources']}")
    if n_docs < gates.get("min_documents", 0):
        failures.append(f"documents {n_docs} < min_documents {gates['min_documents']}")
    if gates.get("require_no_orphan_document_ids") and orphans:
        sample = ", ".join(orphans[:5])
        failures.append(
            f"{len(orphans)} orphan document_id(s) without documents[] row: {sample}"
        )
    min_spans = gates.get("min_observations_with_char_span")
    if min_spans is not None and n_spans < int(min_spans):
        failures.append(
            f"observations_with_char_span={n_spans} < min_observations_with_char_span {min_spans}"
        )
    min_ratio = gates.get("min_char_span_ratio")
    if min_ratio is not None and span_ratio + 1e-12 < float(min_ratio):
        failures.append(
            f"char_span_ratio={span_ratio:.3f} < min_char_span_ratio {min_ratio}"
        )
    # Provisional entity policy (engine 0.1.41+): curated cases should be fully resolved
    if gates.get("require_no_provisional") and n_provisional:
        names = sorted({e.canonical_name for e in provisional if e.canonical_name})
        sample = ", ".join(names[:5])
        more = f" (+{len(names) - 5} more)" if len(names) > 5 else ""
        failures.append(
            f"provisional_entities={n_provisional} but require_no_provisional: {sample}{more}"
        )
    max_prov = gates.get("max_provisional_entities")
    if max_prov is not None and n_provisional > int(max_prov):
        failures.append(
            f"provisional_entities={n_provisional} > max_provisional_entities {max_prov}"
        )

    print(
        f"case={scorecard.get('case_id')} errors={n_err} "
        f"sources={raw} independent={indep} documents={n_docs} "
        f"spans={n_spans}/{n_obs} ({span_ratio:.0%}) "
        f"orphan_doc_ids={len(orphans)} provisional={n_provisional} "
        f"obs_types={sorted(obs_types)} "
        f"lineage={lineage.get('manifest_sha256', '')[:19] if lineage else 'none'}"
    )
    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("OK: scorecard gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

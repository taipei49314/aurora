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
    for flag in ("license", "stage_unresolved", "stage_unresolved_subjects", "provisional_entity_type"):
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

    failures = []
    if n_err > gates.get("import_errors_max", 0):
        failures.append(f"import_errors={n_err} > max {gates['import_errors_max']}")
    for t in gates.get("require_observation_types", []):
        if t not in obs_types:
            failures.append(f"missing observation_type {t}")
    if gates.get("independent_lt_raw") and not (indep < raw):
        failures.append(f"expected independent ({indep}) < raw ({raw})")
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
        f"obs_types={sorted(obs_types)}"
    )
    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("OK: scorecard gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

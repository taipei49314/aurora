#!/usr/bin/env python3
"""Build cases/multisource-iron-air from adapter fixtures + shared LEI crosswalk.

Stacks: patentsview + jobs + news + filings + openalex.
Companies join on external_ids (LEI/domain). Fixture-based only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "adapters" / "fixtures"
OUT = ROOT / "cases" / "multisource-iron-air"

LEI = {
    "FerroGrid Power": "LEI-FERRO-DEMO",
    "OxaCell Systems": "LEI-OXA-DEMO",
    "LongHaul Energy": "LEI-LONG-DEMO",
    "PureChitin Bio": "LEI-PURE-DEMO",
}
DOMAIN = {
    "FerroGrid Power": "ferrogrid.example",
    "OxaCell Systems": "oxacell.example",
    "LongHaul Energy": "longhaul.example",
    "PureChitin Bio": "purechitin.example",
}


def stamp_company_ids(pkg: dict) -> dict:
    for e in pkg.get("entities") or []:
        if e.get("entity_type") != "COMPANY":
            continue
        name = e.get("canonical_name") or ""
        ids = list(e.get("external_ids") or [])
        seen = {(x.get("system"), x.get("id")) for x in ids if isinstance(x, dict)}
        for sys, val in (("lei", LEI.get(name)), ("domain", DOMAIN.get(name))):
            if not val:
                continue
            key = (sys, val)
            if key not in seen:
                ids.append({"system": sys, "id": val})
                seen.add(key)
        e["external_ids"] = ids
    return pkg


def export_snapshot(snap) -> dict:
    name_by_id = {e.entity_id: e.canonical_name for e in snap.entities}
    entities = []
    for e in snap.entities:
        entities.append({
            "entity_type": e.entity_type,
            "canonical_name": e.canonical_name,
            "aliases": list(e.aliases or []),
            "description": e.description,
            "country": e.country,
            "external_ids": list(e.external_ids or []),
            "metadata": dict(e.metadata or {}),
        })
    sources = []
    for src in snap.sources:
        meta = dict(src.metadata or {})
        excerpt = meta.pop("excerpt", "")
        license_s = getattr(src, "license", "") or meta.pop("license", "") or ""
        if license_s:
            meta.pop("license", None)
        sources.append({
            "ref": src.source_id,
            "source_type": src.source_type,
            "publisher": src.publisher,
            "title": src.title,
            "published_at": src.published_at,
            "url_or_local_path": src.url_or_local_path,
            "independence_group": src.independence_group,
            "reliability_tier": src.reliability_tier,
            "language": src.language,
            "license": license_s,
            "excerpt": excerpt,
            "metadata": meta,
        })
    observations = []
    for o in snap.observations:
        meta = {
            k: v for k, v in (o.metadata or {}).items()
            if k not in ("source_type", "independence_group")
        }
        document_id = getattr(o, "document_id", "") or meta.pop("document_id", "") or ""
        if document_id:
            meta.pop("document_id", None)
        char_span = getattr(o, "char_span", None)
        if char_span is None:
            char_span = meta.pop("char_span", None)
        else:
            meta.pop("char_span", None)
        row = {
            "source_ref": o.source_id,
            "observation_type": o.observation_type,
            "subject": name_by_id.get(o.subject_entity, o.subject_entity),
            "object": name_by_id.get(o.object_entity, "") if o.object_entity else "",
            "observed_at": o.observed_at,
            "numeric_value": o.numeric_value,
            "unit": o.unit,
            "text_excerpt": o.text_excerpt,
            "confidence": o.confidence,
            "document_id": document_id,
            "metadata": meta,
        }
        if char_span is not None:
            row["char_span"] = char_span
        observations.append(row)
    documents = []
    for d in getattr(snap, "documents", None) or []:
        documents.append({
            "document_id": d.document_id,
            "source_ref": d.source_id,
            "title": d.title,
            "text": d.text,
            "url_or_local_path": d.url_or_local_path,
            "language": d.language,
            "license": d.license,
            "metadata": dict(d.metadata or {}),
        })
    out = {
        "_comment": (
            "Multi-adapter iron-air demo: patentsview + jobs + news + filings + openalex. "
            "Shared LEI/domain external_ids. Built by scripts/build_multisource_case.py."
        ),
        "entities": entities,
        "sources": sources,
        "observations": observations,
    }
    if documents:
        out["documents"] = documents
    return out


def main() -> int:
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "backend"))
    from adapters import (
        convert_filings,
        convert_jobs,
        convert_news,
        convert_openalex,
        merge_packages,
        strip_package,
    )
    from adapters.patentsview import convert_patentsview
    from aurora import import_package

    packages = [
        stamp_company_ids(
            convert_patentsview(
                json.loads((FIX / "patentsview_sample.json").read_text(encoding="utf-8"))
            )
        ),
        stamp_company_ids(
            convert_jobs(json.loads((FIX / "jobs_sample.json").read_text(encoding="utf-8")))
        ),
        stamp_company_ids(
            convert_news(json.loads((FIX / "news_sample.json").read_text(encoding="utf-8")))
        ),
        stamp_company_ids(
            convert_filings(
                json.loads((FIX / "filings_sample.json").read_text(encoding="utf-8"))
            )
        ),
        stamp_company_ids(
            convert_openalex(
                json.loads((FIX / "openalex_sample.json").read_text(encoding="utf-8"))
            )
        ),
    ]

    merged = stamp_company_ids(merge_packages(packages))
    snap = import_package(strip_package(merged))
    out_pkg = export_snapshot(snap)

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "package.json"
    path.write_text(json.dumps(out_pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    snap2 = import_package(strip_package(out_pkg))
    leis = sum(
        1
        for e in snap2.entities
        for x in (e.external_ids or [])
        if x.get("system") == "lei"
    )
    types = {o.observation_type for o in snap2.observations}
    tiers = {}
    for s in snap2.sources:
        t = (s.reliability_tier or "C").upper()
        tiers[t] = tiers.get(t, 0) + 1
    print(f"wrote {path}")
    print(
        f"entities={len(snap2.entities)} sources={len(snap2.sources)} "
        f"obs={len(snap2.observations)} errors={len(snap2.import_errors)} lei={leis}"
    )
    print(f"types={sorted(types)}")
    print(f"tiers={tiers}")
    print(
        f"independent={snap2.counts.get('independent_source_count')}/"
        f"{snap2.counts.get('raw_source_count')}"
    )
    if snap2.import_errors:
        for e in snap2.import_errors[:8]:
            print(" err", e)
        return 1
    need = {
        "PATENT_ACTIVITY",
        "HIRING_ACTIVITY",
        "SUPPLIER_RELATIONSHIP",
        "CAPEX_ACTIVITY",
        "RESEARCH_ACTIVITY",
    }
    if not need.issubset(types):
        print(f"error: missing {need - types}", file=sys.stderr)
        return 1
    if leis < 3:
        print("error: expected LEI on multiple companies", file=sys.stderr)
        return 1
    if "A" not in tiers:
        print("error: expected tier-A filings sources", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build cases/multisource-iron-air from adapter fixtures + shared LEI crosswalk.

Demonstrates multi-adapter merge where company identity joins on external_ids.
Fixture-based only — not a live crawl.
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
            "excerpt": excerpt,
            "metadata": meta,
        })
    observations = []
    for o in snap.observations:
        meta = {
            k: v for k, v in (o.metadata or {}).items()
            if k not in ("source_type", "independence_group")
        }
        observations.append({
            "source_ref": o.source_id,
            "observation_type": o.observation_type,
            "subject": name_by_id.get(o.subject_entity, o.subject_entity),
            "object": name_by_id.get(o.object_entity, "") if o.object_entity else "",
            "observed_at": o.observed_at,
            "numeric_value": o.numeric_value,
            "unit": o.unit,
            "text_excerpt": o.text_excerpt,
            "confidence": o.confidence,
            "metadata": meta,
        })
    return {
        "_comment": (
            "Multi-adapter iron-air demo with shared LEI/domain external_ids. "
            "Built by scripts/build_multisource_case.py from offline fixtures."
        ),
        "entities": entities,
        "sources": sources,
        "observations": observations,
    }


def main() -> int:
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "backend"))
    from adapters import convert_jobs, convert_news, merge_packages, strip_package
    from adapters.patentsview import convert_patentsview
    from aurora import import_package

    pkg_pat = stamp_company_ids(
        convert_patentsview(json.loads((FIX / "patentsview_sample.json").read_text(encoding="utf-8")))
    )
    pkg_jobs = stamp_company_ids(
        convert_jobs(json.loads((FIX / "jobs_sample.json").read_text(encoding="utf-8")))
    )
    pkg_news = stamp_company_ids(
        convert_news(json.loads((FIX / "news_sample.json").read_text(encoding="utf-8")))
    )

    merged = stamp_company_ids(merge_packages([pkg_pat, pkg_jobs, pkg_news]))
    snap = import_package(strip_package(merged))
    out_pkg = export_snapshot(snap)

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "package.json"
    path.write_text(json.dumps(out_pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # second import of exported package must stay clean
    snap2 = import_package(strip_package(out_pkg))
    leis = sum(
        1
        for e in snap2.entities
        for x in (e.external_ids or [])
        if x.get("system") == "lei"
    )
    types = {o.observation_type for o in snap2.observations}
    print(f"wrote {path}")
    print(
        f"entities={len(snap2.entities)} sources={len(snap2.sources)} "
        f"obs={len(snap2.observations)} errors={len(snap2.import_errors)} lei={leis}"
    )
    print(f"types={sorted(types)}")
    print(
        f"independent={snap2.counts.get('independent_source_count')}/"
        f"{snap2.counts.get('raw_source_count')}"
    )
    if snap2.import_errors:
        for e in snap2.import_errors[:8]:
            print(" err", e)
        return 1
    need = {"PATENT_ACTIVITY", "HIRING_ACTIVITY", "SUPPLIER_RELATIONSHIP"}
    if not need.issubset(types):
        print(f"error: missing {need - types}", file=sys.stderr)
        return 1
    if leis < 3:
        print("error: expected LEI on multiple companies", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

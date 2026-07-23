"""USPTO-shaped patent records -> AURORA import package.

Input is **caller-supplied** JSON (fixture or offline dump). No network I/O.

Expected shape (tolerant of missing optional fields)::

    {
      "patents": [
        {
          "publication_number": "US20220123456A1",   # required
          "family_id": "ironair-ferro-2022",         # optional
          "title": "...",                            # required
          "abstract": "...",                         # optional -> excerpt
          "application_date": "2021-11-02",          # preferred for observed_at
          "publication_date": "2022-04-12",          # source published_at
          "assignees": [{"name": "Acme", "country": "US"}],
          "cpc": ["H01M4/86"],
          "ipc": ["H01M4/00"],
          "url": "https://...",
          "technologies": ["reversible iron oxidation"],  # optional entity names
          "components": ["porous iron electrode"],        # optional
          "materials": ["food-grade iron powder"]         # optional
        }
      ]
    }

Mapping (docs/import-schema.md):
  * source_type = PATENT, reliability_tier = A
  * independence_group = family:<family_id> or patent:<publication_number>
  * published_at = publication_date; observed_at = application_date or publication_date
  * each assignee -> COMPANY entity + PATENT_ACTIVITY observation
  * optional tech/component/material names -> entities + TECHNICAL_DEPENDENCY edges
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .package_util import Package, strip_package

ADAPTER_ID = "uspto-offline"
ADAPTER_VERSION = "0.1.0"


def _date(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    s = str(value).strip()
    return s[:10] if len(s) >= 10 else s


def _norm_codes(raw: Any) -> List[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        return [raw]
    return [str(x) for x in raw if x]


def convert_uspto(raw: dict, *, publisher: str = "USPTO") -> Package:
    """Convert a USPTO-shaped dict into an AURORA import package."""
    patents = raw.get("patents")
    if patents is None:
        raise ValueError("USPTO payload must contain a top-level 'patents' array")
    if not isinstance(patents, list):
        raise ValueError("'patents' must be an array")

    entities: Dict[str, dict] = {}
    sources: List[dict] = []
    observations: List[dict] = []

    def ensure_entity(
        name: str,
        entity_type: str,
        *,
        country: str = "",
        aliases: Optional[List[str]] = None,
        external_ids: Optional[List[dict]] = None,
        description: str = "",
    ) -> str:
        key = name.strip()
        if not key:
            raise ValueError("entity name must be non-empty")
        if key not in entities:
            entities[key] = {
                "entity_type": entity_type,
                "canonical_name": key,
                "aliases": list(aliases or []),
                "description": description,
                "country": country or "",
                "external_ids": list(external_ids or []),
                "metadata": {
                    "extractor_id": ADAPTER_ID,
                    "extractor_version": ADAPTER_VERSION,
                },
            }
        else:
            # merge aliases / country / external_ids if later rows enrich
            ent = entities[key]
            for a in aliases or []:
                if a not in ent["aliases"]:
                    ent["aliases"].append(a)
            if country and not ent.get("country"):
                ent["country"] = country
            if external_ids:
                ids = list(ent.get("external_ids") or [])
                seen = {(x.get("system"), x.get("id")) for x in ids if isinstance(x, dict)}
                for x in external_ids:
                    k = (x.get("system"), x.get("id"))
                    if k not in seen:
                        ids.append(x)
                        seen.add(k)
                ent["external_ids"] = ids
        return key

    for i, patent in enumerate(patents):
        if not isinstance(patent, dict):
            raise ValueError(f"patents[{i}] must be an object")
        pub = (patent.get("publication_number") or patent.get("id") or "").strip()
        title = (patent.get("title") or "").strip()
        if not pub:
            raise ValueError(f"patents[{i}] missing publication_number")
        if not title:
            raise ValueError(f"patents[{i}] missing title")

        abstract = (patent.get("abstract") or patent.get("excerpt") or "").strip()
        app_date = _date(patent.get("application_date") or patent.get("filing_date"))
        pub_date = _date(patent.get("publication_date") or patent.get("published_at"))
        event_date = app_date or pub_date
        family = (patent.get("family_id") or "").strip()
        indep = f"family:{family}" if family else f"patent:{pub}"
        cpc = _norm_codes(patent.get("cpc") or patent.get("classification_codes"))
        ipc = _norm_codes(patent.get("ipc"))
        codes = cpc + [c for c in ipc if c not in cpc]
        url = patent.get("url") or patent.get("url_or_local_path") or f"local://patents/{pub}"

        ref = f"pat-{pub.lower().replace(' ', '')}"
        outlet = "patents.example" if "example" in str(url) else "uspto"
        source_meta: Dict[str, Any] = {
            "external_ids": [{"system": "us_publication", "id": pub}],
            "extractor_id": ADAPTER_ID,
            "extractor_version": ADAPTER_VERSION,
            "license": "public-patent-text",
        }
        if family:
            source_meta["external_ids"].append({"system": "patent_family", "id": family})
            source_meta["family_id"] = family
        if codes:
            source_meta["classification_codes"] = codes
        if app_date and pub_date and app_date != pub_date:
            source_meta["date_policy"] = (
                "observed_at=application_date; published_at=publication_date; "
                "event_date=application_date"
            )

        src_row: Dict[str, Any] = {
            "ref": ref,
            "source_type": "PATENT",
            "publisher": patent.get("publisher") or publisher,
            "title": title,
            "published_at": pub_date,
            "excerpt": abstract[:800] if abstract else title,
            "independence_group": indep,
            "reliability_tier": "A",
            "url_or_local_path": url,
            "language": patent.get("language") or "en",
            "outlet_domain": outlet,  # first-class 0.1.12+
            "metadata": source_meta,
        }
        if family:
            # First-class family_id (engine 0.1.8+); also kept in metadata for older tooling
            src_row["family_id"] = family
        if event_date:
            # First-class event_date (engine 0.1.10+): application/filing date
            src_row["event_date"] = event_date
        sources.append(src_row)

        assignees = patent.get("assignees") or []
        if not assignees and patent.get("assignee"):
            assignees = [patent["assignee"]]
        if not assignees:
            # still emit a research-institute placeholder? Prefer explicit skip of
            # company obs but keep the source for audit — use title-only entity.
            assignees = [{"name": f"Unknown assignee for {pub}", "country": ""}]

        tech_names = [str(t).strip() for t in (patent.get("technologies") or []) if str(t).strip()]
        comp_names = [str(t).strip() for t in (patent.get("components") or []) if str(t).strip()]
        mat_names = [str(t).strip() for t in (patent.get("materials") or []) if str(t).strip()]

        for t in tech_names:
            ensure_entity(t, "TECHNOLOGY")
        for c in comp_names:
            ensure_entity(c, "COMPONENT")
        for m in mat_names:
            ensure_entity(m, "MATERIAL")

        for asg in assignees:
            if isinstance(asg, str):
                asg = {"name": asg}
            name = (asg.get("name") or "").strip()
            if not name:
                continue
            country = (asg.get("country") or "").strip()
            asg_ext = [{"system": "uspto_assignee_name", "id": name}]
            # optional stable ids from enriched dumps
            for x in asg.get("external_ids") or []:
                if isinstance(x, dict) and x.get("system") and x.get("id"):
                    asg_ext.append(x)
            if asg.get("lei"):
                asg_ext.append({"system": "lei", "id": str(asg["lei"])})
            if asg.get("domain"):
                asg_ext.append({"system": "domain", "id": str(asg["domain"])})
            ensure_entity(
                name,
                "COMPANY",
                country=country,
                external_ids=asg_ext,
            )
            evt_id = f"evt_{family or pub}"
            obs_meta: Dict[str, Any] = {
                "document_id": ref,
                "extractor_id": ADAPTER_ID,
                "extractor_version": ADAPTER_VERSION,
            }
            if codes:
                obs_meta["classification_codes"] = codes

            def _obs(otype: str, subject: str, obj, text: str, conf: float) -> Dict[str, Any]:
                return {
                    "source_ref": ref,
                    "observation_type": otype,
                    "subject": subject,
                    "object": obj,
                    "observed_at": event_date,
                    "text_excerpt": text,
                    "confidence": conf,
                    "event_id": evt_id,  # first-class (engine 0.1.11+)
                    "metadata": dict(obs_meta),
                }

            # Primary activity: company filed/published patent
            object_name = tech_names[0] if tech_names else (comp_names[0] if comp_names else None)
            observations.append(_obs(
                "PATENT_ACTIVITY", name, object_name,
                abstract[:400] if abstract else title, 0.9,
            ))

            # Structural edges when adapter was given explicit ontology hooks
            for tech in tech_names:
                observations.append(_obs(
                    "TECHNICAL_DEPENDENCY", name, tech,
                    f"{name} discloses {tech}: {title}", 0.8,
                ))
            for comp in comp_names:
                observations.append(_obs(
                    "TECHNICAL_DEPENDENCY", name, comp,
                    f"{title} — component {comp}", 0.75,
                ))
            for mat in mat_names:
                # component/tech depends on material when both present; else company→material
                subj = comp_names[0] if comp_names else name
                observations.append(_obs(
                    "TECHNICAL_DEPENDENCY", subj, mat,
                    f"Depends on material {mat}", 0.7,
                ))

    pkg = {
        "entities": list(entities.values()),
        "sources": sources,
        "observations": observations,
        "_adapter": {
            "id": ADAPTER_ID,
            "version": ADAPTER_VERSION,
            "source_format": "uspto-offline-v1",
            "patent_count": len(patents),
        },
    }
    # Engine-facing view is strip_package; keep _adapter for diagnostics.
    return pkg


def convert_uspto_file(path: str, **kwargs) -> Package:
    import json
    from pathlib import Path

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return convert_uspto(data, **kwargs)

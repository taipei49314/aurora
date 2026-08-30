"""PatentsView-shaped patent export -> AURORA import package.

Offline only. Accepts common **PatentsView API or PatentsView-derived JSON**
field names. Official bulk downloads are relational TSV tables and must first
be joined into one of these JSON shapes (see ``scripts/extract_patentsview_case.py``).

Supported top-level shapes::

    {"patents": [ {...}, ... ]}
    {"results": [ {...}, ... ]}   # alternate export wrappers

Per-patent fields (any subset; missing optionals are fine)::

    patent_number | patent_id | publication_number
    patent_title | title
    patent_abstract | abstract
    patent_date | publication_date
    app_date | application_date | filing_date | patent_earliest_application_date
    application(s): {filing_date|application_date}
    patent_family_id | family_id
    assignees: [{assignee_organization|raw_assignee_organization|name, ...}]
    cpcs | cpc_current | cpc_at_issue:
        [{cpc_subgroup_id|cpc_group_id|cpc_group|cpc_subclass|cpc_class|cpc_section}]
    inventors: PERSON entities (engine 0.1.16+) + provenance on observations

Conversion reuses ``convert_uspto`` after field normalization so mapping rules
stay single-sourced (import-schema patent conventions).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .package_util import Package
from .uspto import convert_uspto

ADAPTER_ID = "patentsview-offline"
ADAPTER_VERSION = "0.2.0"
SOURCE_FORMAT = "patentsview-api-or-derived-v2"


def _first(*vals: Any) -> Any:
    for v in vals:
        if v not in (None, "", [], {}):
            return v
    return None


def _as_list(val: Any) -> List[Any]:
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


def _joined_name(first: Any, last: Any) -> str:
    return " ".join(
        str(part).strip() for part in (first, last) if part not in (None, "")
    ).strip()


def _assignees(patent: dict) -> List[dict]:
    raw = patent.get("assignees")
    if raw:
        out = []
        for a in _as_list(raw):
            if isinstance(a, str):
                out.append({"name": a, "country": ""})
                continue
            if not isinstance(a, dict):
                continue
            name = _first(
                a.get("assignee_organization"),
                a.get("raw_assignee_organization"),
                a.get("assignee_name"),
                a.get("organization"),
                a.get("name"),
            )
            person_name = _first(
                a.get("assignee_full_name"),
                _joined_name(
                    _first(
                        a.get("assignee_name_first"),
                        a.get("assignee_first_name"),
                        a.get("assignee_individual_name_first"),
                        a.get("raw_assignee_individual_name_first"),
                    ),
                    _first(
                        a.get("assignee_name_last"),
                        a.get("assignee_last_name"),
                        a.get("assignee_individual_name_last"),
                        a.get("raw_assignee_individual_name_last"),
                    ),
                ),
            )
            entity_type = "COMPANY"
            if not name and person_name:
                name = person_name
                entity_type = "PERSON"
            if not name:
                continue
            normalized = {
                "name": str(name).strip(),
                "country": str(
                    _first(a.get("assignee_country"), a.get("country"), "") or ""
                ).strip(),
                "entity_type": entity_type,
            }
            assignee_id = _first(a.get("assignee_id"), a.get("patentsview_assignee_id"))
            if assignee_id:
                normalized["external_ids"] = [
                    {"system": "patentsview_assignee", "id": str(assignee_id).strip()}
                ]
            out.append(normalized)
        if out:
            return out
    # flat PatentsView rows sometimes embed a single assignee_* at top level
    org = _first(
        patent.get("assignee_organization"),
        patent.get("assignee_name"),
    )
    if org:
        return [{
            "name": str(org).strip(),
            "country": str(
                _first(patent.get("assignee_country"), patent.get("country"), "") or ""
            ).strip(),
        }]
    return []


def _cpc_codes(patent: dict) -> List[str]:
    codes: List[str] = []
    for key in (
        "cpcs",
        "cpc",
        "cpc_current",
        "cpc_at_issue",
        "cpc_subgroup_id",
        "classification_codes",
    ):
        val = patent.get(key)
        if val is None:
            continue
        for item in _as_list(val):
            if isinstance(item, str):
                codes.append(item)
            elif isinstance(item, dict):
                code = _first(
                    item.get("cpc_subgroup_id"),
                    item.get("cpc_subgroup"),
                    item.get("cpc_group"),
                    item.get("cpc_group_id"),
                    item.get("cpc_subclass"),
                    item.get("cpc_subclass_id"),
                    item.get("cpc_class"),
                    item.get("cpc_class_id"),
                    item.get("cpc_section"),
                    item.get("cpc_section_id"),
                    item.get("id"),
                    item.get("code"),
                )
                if code:
                    codes.append(str(code))
    # de-dupe preserve order
    seen = set()
    out = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _inventors(patent: dict) -> List[dict]:
    inventors: List[dict] = []
    for inv in _as_list(patent.get("inventors")):
        if isinstance(inv, str):
            if inv.strip():
                inventors.append({"name": inv.strip()})
        elif isinstance(inv, dict):
            n = _first(
                inv.get("inventor_name_full"),
                inv.get("name"),
                _joined_name(
                    inv.get("inventor_name_first"), inv.get("inventor_name_last")
                ),
                inv.get("inventor_last_name"),
            )
            if n:
                normalized = {
                    "name": str(n).strip(),
                    "country": str(
                        _first(inv.get("inventor_country"), inv.get("country"), "")
                        or ""
                    ).strip(),
                }
                inventor_id = _first(
                    inv.get("inventor_id"), inv.get("patentsview_inventor_id")
                )
                if inventor_id:
                    normalized["external_ids"] = [
                        {
                            "system": "patentsview_inventor",
                            "id": str(inventor_id).strip(),
                        }
                    ]
                inventors.append(normalized)
    return inventors


def _application_date(patent: dict) -> Any:
    direct = _first(
        patent.get("patent_earliest_application_date"),
        patent.get("app_date"),
        patent.get("application_date"),
        patent.get("filing_date"),
    )
    if direct:
        return direct
    dates = []
    for key in ("application", "applications"):
        for application in _as_list(patent.get(key)):
            if isinstance(application, dict):
                value = _first(
                    application.get("filing_date"),
                    application.get("application_date"),
                    application.get("app_date"),
                )
                if value:
                    dates.append(value)
    return min(dates, key=lambda value: str(value)) if dates else None


def normalize_patentsview_record(patent: dict) -> dict:
    """Map one PatentsView-like record to the internal USPTO-shaped record."""
    if not isinstance(patent, dict):
        raise ValueError("each patent must be an object")
    pub = _first(
        patent.get("patent_number"),
        patent.get("patent_id"),
        patent.get("publication_number"),
        patent.get("id"),
    )
    title = _first(patent.get("patent_title"), patent.get("title"))
    if not pub:
        raise ValueError("patent missing patent_number/patent_id")
    if not title:
        raise ValueError(f"patent {pub} missing patent_title/title")

    abstract = _first(patent.get("patent_abstract"), patent.get("abstract"), "")
    app_date = _application_date(patent)
    pub_date = _first(patent.get("patent_date"), patent.get("publication_date"))
    family = _first(patent.get("patent_family_id"), patent.get("family_id"), "")

    row: Dict[str, Any] = {
        "publication_number": str(pub).strip(),
        "title": str(title).strip(),
        "abstract": str(abstract or "").strip(),
        "application_date": app_date,
        "publication_date": pub_date,
        "family_id": str(family).strip() if family else "",
        "assignees": _assignees(patent),
        "inventors": _inventors(patent),
        "cpc": _cpc_codes(patent),
        "publisher": patent.get("publisher") or "USPTO",
        "url": _first(
            patent.get("url"),
            patent.get("patent_url"),
            f"https://patents.google.com/patent/US{str(pub).strip()}",
        ),
        "language": patent.get("language") or "en",
        "license": patent.get("license") or "",
        "retrieved_at": patent.get("retrieved_at") or "",
    }
    # optional ontology hooks if present in enriched exports
    for key in ("technologies", "components", "materials"):
        if patent.get(key):
            row[key] = patent[key]
    return row


def patentsview_to_uspto_payload(
    raw: dict, *, lineage: Optional[Dict[str, Any]] = None
) -> dict:
    patents = raw.get("patents")
    if patents is None:
        patents = raw.get("results")
    if patents is None:
        raise ValueError(
            "PatentsView payload must contain top-level 'patents' or 'results' array"
        )
    if not isinstance(patents, list):
        raise ValueError("'patents'/'results' must be an array")

    provenance = raw.get("_provenance") if isinstance(raw.get("_provenance"), dict) else {}
    normalized = []
    for i, p in enumerate(patents):
        try:
            rec = normalize_patentsview_record(p)
        except ValueError as exc:
            raise ValueError(f"patents[{i}]: {exc}") from exc
        rec["publisher"] = _first(
            p.get("publisher") if isinstance(p, dict) else None,
            provenance.get("source_owner"),
            "USPTO PatentsView",
        )
        rec["license"] = _first(
            rec.get("license"),
            (lineage or {}).get("license"),
            provenance.get("license"),
            "",
        )
        rec["retrieved_at"] = _first(
            rec.get("retrieved_at"),
            (lineage or {}).get("retrieved_at"),
            provenance.get("retrieved_at"),
            "",
        )
        rec["url"] = _first(
            p.get("url") if isinstance(p, dict) else None,
            (lineage or {}).get("origin_url"),
            provenance.get("source_url"),
            rec.get("url"),
        )
        normalized.append(rec)
    return {"patents": normalized}


def convert_patentsview(
    raw: dict, *, lineage: Optional[Dict[str, Any]] = None
) -> Package:
    """Convert PatentsView-shaped JSON into an AURORA import package."""
    payload = patentsview_to_uspto_payload(raw, lineage=lineage)
    clean_patents = payload["patents"]
    pkg = convert_uspto({"patents": clean_patents}, publisher="USPTO")
    # Replace the reused USPTO converter identity consistently on every row.
    for collection in ("entities", "sources", "observations", "documents"):
        for row in pkg.get(collection) or []:
            meta = dict(row.get("metadata") or {})
            meta["extractor_id"] = ADAPTER_ID
            meta["extractor_version"] = ADAPTER_VERSION
            if collection == "sources":
                meta["source_format"] = SOURCE_FORMAT
                external_ids = list(meta.get("external_ids") or [])
                patent_ids = [
                    str(item.get("id"))
                    for item in external_ids
                    if isinstance(item, dict)
                    and item.get("system") == "us_publication"
                    and item.get("id")
                ]
                seen = {
                    (item.get("system"), item.get("id"))
                    for item in external_ids
                    if isinstance(item, dict)
                }
                for patent_id in patent_ids:
                    key = ("patentsview_patent", patent_id)
                    if key not in seen:
                        external_ids.append({"system": key[0], "id": key[1]})
                        seen.add(key)
                meta["external_ids"] = external_ids
            if lineage:
                meta["corpus_lineage"] = dict(lineage)
            row["metadata"] = meta

    if lineage:
        pkg["lineage"] = dict(lineage)
        pkg["license"] = lineage.get("license", "")

    pkg["_adapter"] = {
        "id": ADAPTER_ID,
        "version": ADAPTER_VERSION,
        "source_format": SOURCE_FORMAT,
        "patent_count": len(clean_patents),
        "upstream": "USPTO PatentsView",
    }
    return pkg

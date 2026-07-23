"""PatentsView-shaped patent export -> AURORA import package.

Offline only. Accepts the common **PatentsView / patent-bulk JSON** field names
so a real API or bulk export can replace the fixture without code changes.

Supported top-level shapes::

    {"patents": [ {...}, ... ]}
    {"results": [ {...}, ... ]}   # alternate export wrappers

Per-patent fields (any subset; missing optionals are fine)::

    patent_number | patent_id | publication_number
    patent_title | title
    patent_abstract | abstract
    patent_date | publication_date
    app_date | application_date | filing_date
    patent_family_id | family_id
    assignees: [{assignee_organization|assignee_name|name, assignee_country|country}]
    cpcs: [{cpc_subgroup_id|cpc_group_id}]  or cpc: ["H01M4/86", ...]
    inventors: PERSON entities (engine 0.1.16+) + provenance on observations

Conversion reuses ``convert_uspto`` after field normalization so mapping rules
stay single-sourced (import-schema patent conventions).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .package_util import Package
from .uspto import convert_uspto

ADAPTER_ID = "patentsview-offline"
ADAPTER_VERSION = "0.1.1"


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
                a.get("assignee_name"),
                a.get("organization"),
                a.get("name"),
            )
            if not name:
                # person assignee — keep as company-like string for ER, flagged in meta
                name = _first(a.get("assignee_full_name"), a.get("assignee_last_name"))
            if not name:
                continue
            out.append({
                "name": str(name).strip(),
                "country": str(
                    _first(a.get("assignee_country"), a.get("country"), "") or ""
                ).strip(),
            })
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
    for key in ("cpcs", "cpc", "cpc_subgroup_id", "classification_codes"):
        val = patent.get(key)
        if val is None:
            continue
        for item in _as_list(val):
            if isinstance(item, str):
                codes.append(item)
            elif isinstance(item, dict):
                code = _first(
                    item.get("cpc_subgroup_id"),
                    item.get("cpc_group_id"),
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


def _inventor_names(patent: dict) -> List[str]:
    names = []
    for inv in _as_list(patent.get("inventors")):
        if isinstance(inv, str):
            names.append(inv)
        elif isinstance(inv, dict):
            n = _first(
                inv.get("inventor_name_full"),
                inv.get("inventor_last_name"),
                inv.get("name"),
            )
            if n:
                names.append(str(n))
    return names


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
    app_date = _first(
        patent.get("app_date"),
        patent.get("application_date"),
        patent.get("filing_date"),
    )
    pub_date = _first(patent.get("patent_date"), patent.get("publication_date"))
    family = _first(patent.get("patent_family_id"), patent.get("family_id"), "")

    inventors = _inventor_names(patent)
    row: Dict[str, Any] = {
        "publication_number": str(pub).strip(),
        "title": str(title).strip(),
        "abstract": str(abstract or "").strip(),
        "application_date": app_date,
        "publication_date": pub_date,
        "family_id": str(family).strip() if family else "",
        "assignees": _assignees(patent),
        "cpc": _cpc_codes(patent),
        "publisher": patent.get("publisher") or "USPTO",
        "url": _first(
            patent.get("url"),
            patent.get("patent_url"),
            f"https://patents.google.com/patent/US{str(pub).strip()}",
        ),
        "language": patent.get("language") or "en",
    }
    # optional ontology hooks if present in enriched exports
    for key in ("technologies", "components", "materials"):
        if patent.get(key):
            row[key] = patent[key]
    # stash inventors for provenance only (passed through uspto metadata path via re-wrap)
    if inventors:
        row["_inventors"] = inventors
    return row


def patentsview_to_uspto_payload(raw: dict) -> dict:
    patents = raw.get("patents")
    if patents is None:
        patents = raw.get("results")
    if patents is None:
        raise ValueError(
            "PatentsView payload must contain top-level 'patents' or 'results' array"
        )
    if not isinstance(patents, list):
        raise ValueError("'patents'/'results' must be an array")

    normalized = []
    for i, p in enumerate(patents):
        try:
            rec = normalize_patentsview_record(p)
        except ValueError as exc:
            raise ValueError(f"patents[{i}]: {exc}") from exc
        # carry inventors into a side channel for package metadata after convert
        inventors = rec.pop("_inventors", None)
        if inventors:
            rec.setdefault("technologies", rec.get("technologies") or [])
            # do not invent tech from inventors; only store for post-pass
            rec["_inventors"] = inventors
        normalized.append(rec)
    return {"patents": normalized}


def convert_patentsview(raw: dict) -> Package:
    """Convert PatentsView-shaped JSON into an AURORA import package."""
    # Preserve inventors without feeding them into convert_uspto unknown fields badly
    payload = patentsview_to_uspto_payload(raw)
    inventor_by_pub = {}
    clean_patents = []
    for rec in payload["patents"]:
        rec = dict(rec)
        inv = rec.pop("_inventors", None)
        pub = rec["publication_number"]
        if inv:
            inventor_by_pub[pub] = inv
        clean_patents.append(rec)

    # Re-attach inventors so convert_uspto can emit PERSON entities (0.1.16+)
    for rec in clean_patents:
        pub = rec.get("publication_number")
        if pub and pub in inventor_by_pub:
            rec["inventors"] = [{"name": n} for n in inventor_by_pub[pub]]

    pkg = convert_uspto({"patents": clean_patents}, publisher="USPTO")
    # annotate sources with patentsview provenance
    for src in pkg["sources"]:
        meta = dict(src.get("metadata") or {})
        meta["extractor_id"] = ADAPTER_ID
        meta["extractor_version"] = ADAPTER_VERSION
        meta["source_format"] = "patentsview-compatible-v1"
        src["metadata"] = meta

    pkg["_adapter"] = {
        "id": ADAPTER_ID,
        "version": ADAPTER_VERSION,
        "source_format": "patentsview-compatible-v1",
        "patent_count": len(clean_patents),
        "upstream": "uspto-offline",
    }
    return pkg

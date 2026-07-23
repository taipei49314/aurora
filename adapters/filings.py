"""Company filing / material-event records -> AURORA import package.

Offline only. Expected shape::

    {
      "filings": [
        {
          "id": "fg-8k-2024",                    # required
          "company": "FerroGrid Power",          # required
          "title": "Material event: capex…",     # required
          "body": "…",                           # optional excerpt
          "filed_at": "2024-06-20",
          "form": "8-K",                         # optional
          "observation_type": "CAPEX_ACTIVITY",  # or CAPACITY_EXPANSION, etc.
          "amount": 120000000,
          "currency": "USD",
          "object": "FerroGrid Arizona pilot plant",
          "object_type": "FACILITY",
          "url": "…",
          "domain": "ferrogrid.example",
          "lei": "LEI-FERRO-DEMO"
        }
      ]
    }

Defaults to COMPANY_FILING source, reliability_tier A, CAPEX_ACTIVITY when type omitted.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .package_util import Package

ADAPTER_ID = "filings-offline"
ADAPTER_VERSION = "0.1.0"

_ALLOWED_TYPES = {
    "CAPEX_ACTIVITY",
    "CAPACITY_EXPANSION",
    "PRODUCT_LAUNCH",
    "STRATEGIC_INVESTMENT",
    "DEMAND_SIGNAL",
    "SHUTDOWN_SIGNAL",
    "CANCELLATION_SIGNAL",
    "REGULATORY_SUPPORT",
}


def _date(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    s = str(value).strip()
    return s[:10] if len(s) >= 10 else s


def convert_filings(raw: dict) -> Package:
    filings = raw.get("filings")
    if filings is None:
        raise ValueError("filings payload must contain top-level 'filings' array")
    if not isinstance(filings, list):
        raise ValueError("'filings' must be an array")

    entities: Dict[str, dict] = {}
    sources: List[dict] = []
    observations: List[dict] = []

    def ensure(name: str, etype: str, *, country: str = "", external_ids: Optional[List[dict]] = None) -> str:
        key = name.strip()
        if not key:
            raise ValueError("entity name empty")
        if key not in entities:
            entities[key] = {
                "entity_type": etype,
                "canonical_name": key,
                "aliases": [],
                "description": "",
                "country": country or "",
                "external_ids": list(external_ids or []),
                "metadata": {
                    "extractor_id": ADAPTER_ID,
                    "extractor_version": ADAPTER_VERSION,
                },
            }
        else:
            ent = entities[key]
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

    for i, row in enumerate(filings):
        if not isinstance(row, dict):
            raise ValueError(f"filings[{i}] must be an object")
        fid = (row.get("id") or "").strip()
        company = (row.get("company") or "").strip()
        title = (row.get("title") or "").strip()
        if not fid:
            raise ValueError(f"filings[{i}] missing id")
        if not company:
            raise ValueError(f"filings[{i}] missing company")
        if not title:
            raise ValueError(f"filings[{i}] missing title")

        body = (row.get("body") or row.get("excerpt") or "").strip()
        filed = _date(row.get("filed_at") or row.get("published_at") or row.get("observed_at"))
        otype = (row.get("observation_type") or "CAPEX_ACTIVITY").strip().upper()
        if otype not in _ALLOWED_TYPES:
            raise ValueError(f"filings[{i}] unknown observation_type {otype}")

        domain = (row.get("domain") or "").strip()
        lei = (row.get("lei") or "").strip()
        ext = []
        if lei:
            ext.append({"system": "lei", "id": lei})
        if domain:
            ext.append({"system": "domain", "id": domain})
        ensure(company, "COMPANY", country=str(row.get("country") or ""), external_ids=ext)

        obj_name = (row.get("object") or "").strip() or None
        obj_type = (row.get("object_type") or "FACILITY").strip()
        if obj_name:
            ensure(obj_name, obj_type if obj_type else "FACILITY")

        ref = f"filing-{fid.lower().replace(' ', '-')}"
        form = (row.get("form") or "").strip()
        publisher = row.get("publisher") or company
        indep = f"domain:{domain}" if domain else f"filing:{fid}"

        meta: Dict[str, Any] = {
            "extractor_id": ADAPTER_ID,
            "extractor_version": ADAPTER_VERSION,
            "external_ids": [{"system": "filing_id", "id": fid}],
        }
        if form:
            meta["form"] = form
        if row.get("currency"):
            meta["currency"] = row["currency"]
        if row.get("amount") is not None:
            meta["amount_original"] = row["amount"]

        src_row: Dict[str, Any] = {
            "ref": ref,
            "source_type": "COMPANY_FILING",
            "publisher": publisher,
            "title": title if not form else f"[{form}] {title}",
            "published_at": filed,
            "excerpt": (body or title)[:800],
            "independence_group": indep,
            "reliability_tier": row.get("reliability_tier") or "A",
            "url_or_local_path": row.get("url") or f"local://filings/{fid}",
            "language": row.get("language") or "en",
            "metadata": meta,
        }
        if domain:
            src_row["outlet_domain"] = domain  # first-class 0.1.12+
        sources.append(src_row)

        obs: Dict[str, Any] = {
            "source_ref": ref,
            "observation_type": otype,
            "subject": company,
            "object": obj_name,
            "observed_at": filed,
            "text_excerpt": (body or title)[:400],
            "confidence": float(row.get("confidence") or 0.9),
            "event_id": f"evt_{fid}",
            "document_id": ref,  # first-class 0.1.15+
            "metadata": {
                "extractor_id": ADAPTER_ID,
            },
        }
        if row.get("amount") is not None:
            try:
                obs["numeric_value"] = float(row["amount"])
                obs["unit"] = str(row.get("currency") or "USD")
            except (TypeError, ValueError):
                pass
        observations.append(obs)

    return {
        "entities": list(entities.values()),
        "sources": sources,
        "observations": observations,
        "_adapter": {
            "id": ADAPTER_ID,
            "version": ADAPTER_VERSION,
            "source_format": "filings-offline-v1",
            "filing_count": len(filings),
        },
    }

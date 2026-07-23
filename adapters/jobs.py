"""Job-board shaped postings -> AURORA import package.

Offline only. Expected shape::

    {
      "postings": [
        {
          "id": "job-ferro-ee",                 # required (stable ref seed)
          "company": "FerroGrid Power",         # required
          "title": "Electrochemical engineer",  # required
          "description": "...",                 # optional -> excerpt / text
          "posted_at": "2024-03-01",
          "closed_at": "2024-09-01",
          "openings": 6,
          "location": {"country": "US", "region": "AZ"},
          "url": "https://...",
          "domain": "ferrogrid.example",
          "related_technologies": ["reversible iron oxidation"],
          "related_components": ["porous iron electrode"]
        }
      ]
    }
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .package_util import Package, ensure_documents

ADAPTER_ID = "jobs-offline"
ADAPTER_VERSION = "0.1.1"


def _date(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    s = str(value).strip()
    return s[:10] if len(s) >= 10 else s


def convert_jobs(raw: dict) -> Package:
    postings = raw.get("postings")
    if postings is None:
        raise ValueError("jobs payload must contain a top-level 'postings' array")
    if not isinstance(postings, list):
        raise ValueError("'postings' must be an array")

    entities: Dict[str, dict] = {}
    sources: List[dict] = []
    observations: List[dict] = []

    def ensure(
        name: str,
        etype: str,
        *,
        country: str = "",
        external_ids: Optional[List[dict]] = None,
        meta_extra: Optional[dict] = None,
    ) -> str:
        key = name.strip()
        if not key:
            raise ValueError("entity name must be non-empty")
        if key not in entities:
            meta = {
                "extractor_id": ADAPTER_ID,
                "extractor_version": ADAPTER_VERSION,
            }
            if meta_extra:
                # do not bury external_ids only in metadata
                extra = dict(meta_extra)
                ext = list(external_ids or []) + list(extra.pop("external_ids", None) or [])
                meta.update(extra)
            else:
                ext = list(external_ids or [])
            entities[key] = {
                "entity_type": etype,
                "canonical_name": key,
                "aliases": [],
                "description": "",
                "country": country or "",
                "external_ids": ext,
                "metadata": meta,
            }
        else:
            ent = entities[key]
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

    for i, row in enumerate(postings):
        if not isinstance(row, dict):
            raise ValueError(f"postings[{i}] must be an object")
        job_id = (row.get("id") or "").strip()
        company = (row.get("company") or "").strip()
        title = (row.get("title") or "").strip()
        if not job_id:
            raise ValueError(f"postings[{i}] missing id")
        if not company:
            raise ValueError(f"postings[{i}] missing company")
        if not title:
            raise ValueError(f"postings[{i}] missing title")

        desc = (row.get("description") or row.get("excerpt") or "").strip()
        posted = _date(row.get("posted_at") or row.get("published_at"))
        closed = _date(row.get("closed_at"))
        loc = row.get("location") or {}
        if isinstance(loc, str):
            loc = {"raw": loc}
        country = (loc.get("country") or row.get("country") or "").strip()
        domain = (row.get("domain") or row.get("outlet_domain") or "").strip()
        if not domain and row.get("url"):
            # best-effort host — adapters stay deterministic, no network
            try:
                from urllib.parse import urlparse

                host = urlparse(str(row["url"])).hostname or ""
                domain = host
            except Exception:  # noqa: BLE001
                domain = ""
        indep = f"domain:{domain}" if domain else f"job:{job_id}"
        ref = f"job-{job_id.lower().replace(' ', '-')}"
        openings = row.get("openings")
        try:
            openings_n = float(openings) if openings is not None else None
        except (TypeError, ValueError):
            openings_n = None

        ensure(
            company,
            "COMPANY",
            country=country,
            external_ids=(
                [{"system": "domain", "id": domain}] if domain else []
            ),
            meta_extra={"domains": [domain] if domain else []},
        )
        techs = [str(t).strip() for t in (row.get("related_technologies") or []) if str(t).strip()]
        comps = [str(t).strip() for t in (row.get("related_components") or []) if str(t).strip()]
        for t in techs:
            ensure(t, "TECHNOLOGY")
        for c in comps:
            ensure(c, "COMPONENT")

        source_meta: Dict[str, Any] = {
            "extractor_id": ADAPTER_ID,
            "extractor_version": ADAPTER_VERSION,
            "external_ids": [{"system": "job_id", "id": job_id}],
        }
        if closed:
            source_meta["valid_to"] = closed
        if posted:
            source_meta["valid_from"] = posted

        # Normalize location → first-class geo (engine 0.1.13+)
        geo: Dict[str, Any] = {}
        if isinstance(loc, dict):
            for k in ("country", "region", "city", "raw", "jurisdiction", "state", "admin1"):
                if loc.get(k) not in (None, ""):
                    key = "region" if k in ("state", "admin1") else k
                    geo.setdefault(key, str(loc[k]).strip())
        if country and "country" not in geo:
            geo["country"] = country

        src_row: Dict[str, Any] = {
            "ref": ref,
            "source_type": "JOB_POSTING",
            "publisher": row.get("publisher") or f"{company} careers",
            "title": title,
            "published_at": posted,
            "excerpt": (desc or title)[:800],
            "independence_group": indep,
            "reliability_tier": row.get("reliability_tier") or "B",
            "url_or_local_path": row.get("url") or f"local://jobs/{job_id}",
            "language": row.get("language") or "en",
            "metadata": source_meta,
        }
        if domain:
            src_row["outlet_domain"] = domain  # first-class 0.1.12+
        if geo:
            src_row["geo"] = dict(geo)
        sources.append(src_row)

        obj = comps[0] if comps else (techs[0] if techs else None)
        obs_meta: Dict[str, Any] = {
            "extractor_id": ADAPTER_ID,
            "extractor_version": ADAPTER_VERSION,
        }
        if posted:
            obs_meta["valid_from"] = posted
        if closed:
            obs_meta["valid_to"] = closed

        obs: Dict[str, Any] = {
            "source_ref": ref,
            "observation_type": "HIRING_ACTIVITY",
            "subject": company,
            "object": obj,
            "event_id": f"evt_hire_{job_id}",
            "document_id": ref,  # first-class 0.1.15+
            "observed_at": posted,
            "text_excerpt": (desc or title)[:400],
            "confidence": float(row.get("confidence") or 0.8),
            "metadata": obs_meta,
        }
        if geo:
            obs["geo"] = dict(geo)
        if openings_n is not None:
            obs["numeric_value"] = openings_n
            obs["unit"] = "openings"
        observations.append(obs)

        for tech in techs:
            dep: Dict[str, Any] = {
                "source_ref": ref,
                "observation_type": "TECHNICAL_DEPENDENCY",
                "subject": company,
                "object": tech,
                "observed_at": posted,
                "text_excerpt": f"Hiring for skills related to {tech}: {title}",
                "confidence": 0.55,
                "event_id": f"evt_hire_{job_id}",
                "document_id": ref,
                "metadata": dict(obs_meta),
            }
            if geo:
                dep["geo"] = dict(geo)
            observations.append(dep)

    return ensure_documents({
        "entities": list(entities.values()),
        "sources": sources,
        "observations": observations,
        "_adapter": {
            "id": ADAPTER_ID,
            "version": ADAPTER_VERSION,
            "source_format": "jobs-offline-v1",
            "posting_count": len(postings),
        },
    })

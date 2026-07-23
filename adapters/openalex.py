"""OpenAlex-shaped works dump -> AURORA import package.

Offline only. Accepts a simplified OpenAlex works export::

    {
      "results": [   # or "works"
        {
          "id": "https://openalex.org/W123",
          "doi": "https://doi.org/10.1234/x",
          "title": "...",
          "publication_date": "2022-01-15",
          "abstract_inverted_index": null,   # optional
          "abstract": "...",                 # preferred if present
          "authorships": [
            {"institutions": [{"display_name": "MIT", "country_code": "US", "id": "https://openalex.org/I123"}]}
          ],
          "primary_location": {"source": {"display_name": "Nature"}},
          "type": "article"
        }
      ]
    }

Mapping:
  * source_type = PAPER, reliability_tier = B
  * observation RESEARCH_ACTIVITY on institution entities (and optional topic keywords in text)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .package_util import Package

ADAPTER_ID = "openalex-offline"
ADAPTER_VERSION = "0.1.0"


def _date(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    s = str(value).strip()
    return s[:10] if len(s) >= 10 else s


def _abstract_from_inverted(idx: Any) -> str:
    """Rebuild abstract from OpenAlex inverted index if needed."""
    if not isinstance(idx, dict) or not idx:
        return ""
    # map position -> token
    positions: Dict[int, str] = {}
    for token, poss in idx.items():
        if not isinstance(poss, list):
            continue
        for p in poss:
            try:
                positions[int(p)] = str(token)
            except (TypeError, ValueError):
                continue
    if not positions:
        return ""
    return " ".join(positions[i] for i in sorted(positions))


def _openalex_id_tail(url_or_id: str) -> str:
    s = (url_or_id or "").strip()
    if "/" in s:
        return s.rstrip("/").split("/")[-1]
    return s


def convert_openalex(raw: dict) -> Package:
    works = raw.get("results")
    if works is None:
        works = raw.get("works")
    if works is None:
        raise ValueError("OpenAlex payload must contain top-level 'results' or 'works' array")
    if not isinstance(works, list):
        raise ValueError("'results'/'works' must be an array")

    entities: Dict[str, dict] = {}
    sources: List[dict] = []
    observations: List[dict] = []

    def ensure_inst(name: str, *, country: str = "", openalex_id: str = "") -> str:
        key = name.strip()
        if not key:
            raise ValueError("institution name empty")
        if key not in entities:
            ext = []
            if openalex_id:
                ext.append({"system": "openalex_org", "id": _openalex_id_tail(openalex_id)})
            entities[key] = {
                "entity_type": "UNIVERSITY" if "univ" in key.lower() or "institute" in key.lower() else "RESEARCH_INSTITUTE",
                "canonical_name": key,
                "aliases": [],
                "description": "",
                "country": country or "",
                "external_ids": ext,
                "metadata": {
                    "extractor_id": ADAPTER_ID,
                    "extractor_version": ADAPTER_VERSION,
                },
            }
        else:
            ent = entities[key]
            if country and not ent.get("country"):
                ent["country"] = country
            if openalex_id:
                ids = list(ent.get("external_ids") or [])
                tail = _openalex_id_tail(openalex_id)
                if not any(x.get("system") == "openalex_org" and x.get("id") == tail for x in ids):
                    ids.append({"system": "openalex_org", "id": tail})
                    ent["external_ids"] = ids
        return key

    for i, w in enumerate(works):
        if not isinstance(w, dict):
            raise ValueError(f"works[{i}] must be an object")
        wid = _openalex_id_tail(str(w.get("id") or w.get("work_id") or f"work-{i}"))
        title = (w.get("title") or w.get("display_name") or "").strip()
        if not title:
            raise ValueError(f"works[{i}] missing title")
        abstract = (w.get("abstract") or "").strip()
        if not abstract:
            abstract = _abstract_from_inverted(w.get("abstract_inverted_index"))
        pub_date = _date(w.get("publication_date") or w.get("from_publication_date"))
        doi = (w.get("doi") or "").strip()
        if doi.startswith("https://doi.org/"):
            doi_id = doi.replace("https://doi.org/", "")
        else:
            doi_id = doi
        venue = ""
        pl = w.get("primary_location") or {}
        if isinstance(pl, dict):
            src = pl.get("source") or {}
            if isinstance(src, dict):
                venue = (src.get("display_name") or "").strip()
        publisher = venue or "OpenAlex"
        ref = f"oa-{wid.lower()}"

        source_meta: Dict[str, Any] = {
            "extractor_id": ADAPTER_ID,
            "extractor_version": ADAPTER_VERSION,
            "source_format": "openalex-works-v1",
            "external_ids": [{"system": "openalex_work", "id": wid}],
        }
        if doi_id:
            source_meta["external_ids"].append({"system": "doi", "id": doi_id})

        # OpenAlex works are often OA; prefer work-level license when present
        license_s = ""
        for key in ("license", "open_access"):
            val = w.get(key)
            if isinstance(val, dict):
                license_s = (val.get("license") or val.get("oa_status") or "").strip()
            elif isinstance(val, str):
                license_s = val.strip()
            if license_s:
                break
        if not license_s:
            license_s = "openalex-unknown"

        sources.append({
            "ref": ref,
            "source_type": "PAPER",
            "publisher": publisher,
            "title": title,
            "published_at": pub_date,
            "excerpt": (abstract or title)[:800],
            "independence_group": f"doi:{doi_id}" if doi_id else f"openalex:{wid}",
            "reliability_tier": "B",
            "url_or_local_path": doi or w.get("id") or f"local://openalex/{wid}",
            "language": "en",
            "license": license_s,  # first-class 0.1.14+
            "metadata": source_meta,
        })

        institutions = []
        for auth in w.get("authorships") or []:
            if not isinstance(auth, dict):
                continue
            for inst in auth.get("institutions") or []:
                if not isinstance(inst, dict):
                    continue
                name = (inst.get("display_name") or inst.get("name") or "").strip()
                if not name:
                    continue
                country = (inst.get("country_code") or "").strip()
                oid = (inst.get("id") or "").strip()
                institutions.append((name, country, oid))

        if not institutions:
            # still emit research activity under a synthetic holder so the paper is not lost
            institutions.append((f"Authors of {wid}", "", ""))

        seen_inst = set()
        for name, country, oid in institutions:
            if name in seen_inst:
                continue
            seen_inst.add(name)
            ensure_inst(name, country=country, openalex_id=oid)
            observations.append({
                "source_ref": ref,
                "observation_type": "RESEARCH_ACTIVITY",
                "subject": name,
                "object": None,
                "observed_at": pub_date,
                "text_excerpt": (abstract or title)[:400],
                "confidence": 0.75,
                "document_id": ref,  # first-class 0.1.15+
                "metadata": {
                    "extractor_id": ADAPTER_ID,
                    "work_id": wid,
                    "doi": doi_id or None,
                },
            })

    return {
        "entities": list(entities.values()),
        "sources": sources,
        "observations": observations,
        "_adapter": {
            "id": ADAPTER_ID,
            "version": ADAPTER_VERSION,
            "source_format": "openalex-works-v1",
            "work_count": len(works),
        },
    }

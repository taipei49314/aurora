"""News / wire articles -> AURORA import package.

Offline only. Supports declared wire syndication via ``wire_id`` and
``is_reprint_of`` so independence is not inflated by reprints.

Expected shape::

    {
      "articles": [
        {
          "id": "art-1",                         # required
          "title": "...",                        # required
          "body": "...",                         # optional excerpt
          "published_at": "2024-07-02",
          "publisher": "Example Reuter Wire",
          "outlet_domain": "news.example",
          "wire_id": "example-reuter",           # shared across reprints
          "is_reprint_of": null,                 # or primary article id
          "url": "https://...",
          "event_id": "evt_supply_2024",
          "reliability_tier": "C",
          "claims": [                            # required for structured obs
            {
              "observation_type": "SUPPLIER_RELATIONSHIP",
              "subject": "FerroGrid Power",
              "object": "PureChitin Bio",
              "confidence": 0.85
            }
          ]
        }
      ]
    }
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .package_util import Package

ADAPTER_ID = "news-offline"
ADAPTER_VERSION = "0.1.0"

# Entity type hints when claims introduce free names
_DEFAULT_ENTITY_TYPE = "COMPANY"

_RELATIONAL = {
    "SUPPLIER_RELATIONSHIP",
    "CUSTOMER_RELATIONSHIP",
    "TECHNICAL_DEPENDENCY",
    "STRATEGIC_INVESTMENT",
}


def _date(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    s = str(value).strip()
    return s[:10] if len(s) >= 10 else s


def convert_news(raw: dict) -> Package:
    articles = raw.get("articles")
    if articles is None:
        raise ValueError("news payload must contain a top-level 'articles' array")
    if not isinstance(articles, list):
        raise ValueError("'articles' must be an array")

    entities: Dict[str, dict] = {}
    sources: List[dict] = []
    observations: List[dict] = []
    id_to_ref: Dict[str, str] = {}
    id_to_wire: Dict[str, str] = {}

    def ensure(name: str, etype: str = _DEFAULT_ENTITY_TYPE, **extra) -> str:
        key = name.strip()
        if not key:
            raise ValueError("entity name must be non-empty")
        if key not in entities:
            meta = {
                "extractor_id": ADAPTER_ID,
                "extractor_version": ADAPTER_VERSION,
            }
            meta.update(extra.get("metadata") or {})
            ext = list(extra.get("external_ids") or [])
            entities[key] = {
                "entity_type": extra.get("entity_type") or etype,
                "canonical_name": key,
                "aliases": list(extra.get("aliases") or []),
                "description": extra.get("description") or "",
                "country": extra.get("country") or "",
                "external_ids": ext,
                "metadata": meta,
            }
        return key

    # First pass: assign refs and independence groups
    for i, art in enumerate(articles):
        if not isinstance(art, dict):
            raise ValueError(f"articles[{i}] must be an object")
        art_id = (art.get("id") or "").strip()
        title = (art.get("title") or "").strip()
        if not art_id:
            raise ValueError(f"articles[{i}] missing id")
        if not title:
            raise ValueError(f"articles[{i}] missing title")
        ref = f"news-{art_id.lower().replace(' ', '-')}"
        id_to_ref[art_id] = ref
        wire = (art.get("wire_id") or "").strip()
        id_to_wire[art_id] = wire

    for i, art in enumerate(articles):
        art_id = (art.get("id") or "").strip()
        title = (art.get("title") or "").strip()
        body = (art.get("body") or art.get("excerpt") or "").strip()
        published = _date(art.get("published_at"))
        publisher = (art.get("publisher") or "Unknown outlet").strip()
        domain = (art.get("outlet_domain") or art.get("domain") or "").strip()
        wire = id_to_wire.get(art_id) or ""
        reprint_of = (art.get("is_reprint_of") or "").strip() or None
        event_id = (art.get("event_id") or "").strip()
        ref = id_to_ref[art_id]
        tier = art.get("reliability_tier") or ("D" if reprint_of else "C")

        # Independence: reprints inherit primary wire group; else wire: or domain:
        if reprint_of:
            primary_wire = id_to_wire.get(reprint_of) or wire
            if primary_wire:
                indep = f"wire:{primary_wire}"
            elif reprint_of in id_to_ref:
                indep = f"reprint:{reprint_of}"
            else:
                indep = f"wire:{wire}" if wire else f"domain:{domain or art_id}"
            # Prefer matching primary title/body for near-dup when missing
            primary = next((a for a in articles if a.get("id") == reprint_of), None)
            if primary is not None:
                if not body:
                    body = (primary.get("body") or primary.get("excerpt") or "").strip()
                if title == (primary.get("title") or "").strip() or art.get("mirror_title"):
                    title = (primary.get("title") or title).strip()
                    body = (primary.get("body") or primary.get("excerpt") or body).strip()
        elif wire:
            indep = f"wire:{wire}"
        elif domain:
            indep = f"domain:{domain}"
        else:
            indep = f"news:{art_id}"

        source_meta: Dict[str, Any] = {
            "extractor_id": ADAPTER_ID,
            "extractor_version": ADAPTER_VERSION,
            "external_ids": [{"system": "article_id", "id": art_id}],
        }
        if domain:
            source_meta["outlet_domain"] = domain
        if wire:
            source_meta["wire_id"] = wire
        if reprint_of:
            source_meta["is_reprint_of"] = reprint_of
            source_meta["primary_ref"] = id_to_ref.get(reprint_of)
        if event_id:
            source_meta["event_id"] = event_id

        sources.append({
            "ref": ref,
            "source_type": "NEWS",
            "publisher": publisher,
            "title": title,
            "published_at": published,
            "excerpt": (body or title)[:800],
            "independence_group": indep,
            "reliability_tier": tier,
            "url_or_local_path": art.get("url") or f"local://news/{art_id}",
            "language": art.get("language") or "en",
            "metadata": source_meta,
        })

        claims = art.get("claims") or []
        if not isinstance(claims, list):
            raise ValueError(f"articles[{i}].claims must be an array")
        # entity_types optional map on article
        type_hints = art.get("entity_types") or {}

        for j, claim in enumerate(claims):
            if not isinstance(claim, dict):
                raise ValueError(f"articles[{i}].claims[{j}] must be an object")
            otype = (claim.get("observation_type") or "").strip()
            subject = (claim.get("subject") or "").strip()
            if not otype:
                raise ValueError(f"articles[{i}].claims[{j}] missing observation_type")
            if not subject:
                raise ValueError(f"articles[{i}].claims[{j}] missing subject")
            obj = (claim.get("object") or "").strip() or None
            subj_type = type_hints.get(subject) or claim.get("subject_type") or _DEFAULT_ENTITY_TYPE
            ensure(
                subject,
                subj_type,
                external_ids=list(claim.get("subject_external_ids") or []),
            )
            if obj:
                obj_type = type_hints.get(obj) or claim.get("object_type") or (
                    "COMPANY" if otype in _RELATIONAL else "TECHNOLOGY"
                )
                if claim.get("object_type"):
                    obj_type = claim["object_type"]
                ensure(
                    obj,
                    obj_type,
                    external_ids=list(claim.get("object_external_ids") or []),
                )

            obs_meta: Dict[str, Any] = {
                "document_id": ref,
                "extractor_id": ADAPTER_ID,
                "extractor_version": ADAPTER_VERSION,
                "char_span": claim.get("char_span"),
            }
            if event_id:
                obs_meta["event_id"] = event_id
            if reprint_of:
                obs_meta["is_reprint_of"] = reprint_of

            text = (claim.get("text_excerpt") or body or title)[:400]
            conf = float(claim.get("confidence") or (0.7 if reprint_of else 0.8))
            observations.append({
                "source_ref": ref,
                "observation_type": otype,
                "subject": subject,
                "object": obj,
                "observed_at": _date(claim.get("observed_at")) or published,
                "text_excerpt": text,
                "confidence": conf,
                "metadata": {k: v for k, v in obs_meta.items() if v is not None},
            })

    return {
        "entities": list(entities.values()),
        "sources": sources,
        "observations": observations,
        "_adapter": {
            "id": ADAPTER_ID,
            "version": ADAPTER_VERSION,
            "source_format": "news-offline-v1",
            "article_count": len(articles),
        },
    }

"""Helpers for composing AURORA import packages."""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional


Package = Dict[str, Any]

# Keep in sync with backend/aurora/char_span.py (adapters stay backend-independent).
_MIN_EXCERPT_LEN = 4


def align_char_span(document_text: str, text_excerpt: str) -> Optional[List[int]]:
    """Locate *text_excerpt* in *document_text*; return ``[start, end]`` or None.

    Deterministic: exact → case-insensitive → whitespace-flexible regex.
    Mirrors ``aurora.char_span.align_char_span`` so adapter packages ship spans
    before import (engine 0.1.20+).
    """
    doc = document_text if isinstance(document_text, str) else ""
    ex = (text_excerpt if isinstance(text_excerpt, str) else "").strip()
    if not doc or not ex or len(ex) < _MIN_EXCERPT_LEN:
        return None
    idx = doc.find(ex)
    if idx >= 0:
        return [idx, idx + len(ex)]
    idx = doc.lower().find(ex.lower())
    if idx >= 0:
        return [idx, idx + len(ex)]
    tokens = [t for t in re.split(r"\s+", ex) if t]
    if tokens:
        pattern = r"\s+".join(re.escape(t) for t in tokens)
        try:
            m = re.search(pattern, doc, flags=re.IGNORECASE | re.DOTALL)
        except re.error:
            m = None
        if m is not None:
            return [m.start(), m.end()]
    return None


def align_observation_char_spans(pkg: Package) -> Package:
    """Fill missing observation ``char_span`` from document text + text_excerpt."""
    out = dict(pkg)
    docs = {
        (d.get("document_id") or d.get("id") or "").strip(): d
        for d in (out.get("documents") or [])
        if isinstance(d, dict) and (d.get("document_id") or d.get("id"))
    }
    if not docs:
        return out
    observations = []
    for o in out.get("observations") or []:
        if not isinstance(o, dict):
            observations.append(o)
            continue
        row = dict(o)
        if row.get("char_span") not in (None, ""):
            observations.append(row)
            continue
        did = (row.get("document_id") or (row.get("metadata") or {}).get("document_id") or "").strip()
        if not did or did not in docs:
            observations.append(row)
            continue
        d = docs[did]
        text = d.get("text") or d.get("body") or ""
        excerpt = row.get("text_excerpt") or ""
        span = align_char_span(text, excerpt)
        if span is not None:
            row["char_span"] = span
            meta = dict(row.get("metadata") or {})
            meta["char_span_auto"] = True
            row["metadata"] = meta
        observations.append(row)
    out["observations"] = observations
    return out



def strip_package(raw: dict) -> Package:
    """Keep only the arrays the engine accepts (entities/sources/observations/documents)."""
    out: Package = {
        "entities": list(raw.get("entities") or []),
        "sources": list(raw.get("sources") or []),
        "observations": list(raw.get("observations") or []),
    }
    docs = raw.get("documents")
    if docs:
        out["documents"] = list(docs)
    return out


def _entity_key(row: dict) -> tuple:
    return (row.get("entity_type", ""), (row.get("canonical_name") or "").strip().lower())


def _merge_entity(a: dict, b: dict) -> dict:
    out = dict(a)
    aliases = list(out.get("aliases") or [])
    for alias in b.get("aliases") or []:
        if alias not in aliases:
            aliases.append(alias)
    out["aliases"] = aliases
    if not out.get("description") and b.get("description"):
        out["description"] = b["description"]
    if not out.get("country") and b.get("country"):
        out["country"] = b["country"]
    # first-class external_ids (preferred) + legacy metadata.external_ids
    ids = list(out.get("external_ids") or [])
    seen = {(x.get("system"), x.get("id")) for x in ids if isinstance(x, dict)}
    for src in (
        b.get("external_ids") or [],
        (out.get("metadata") or {}).get("external_ids") or [],
        (b.get("metadata") or {}).get("external_ids") or [],
    ):
        for x in src:
            if not isinstance(x, dict):
                continue
            key = (x.get("system"), x.get("id"))
            if key not in seen and key[0] and key[1]:
                ids.append(x)
                seen.add(key)
    out["external_ids"] = ids
    meta = dict(out.get("metadata") or {})
    other = dict(b.get("metadata") or {})
    meta.pop("external_ids", None)
    other.pop("external_ids", None)
    for k, v in other.items():
        if k not in meta:
            meta[k] = v
    out["metadata"] = meta
    return out


def _merge_document(a: dict, b: dict) -> dict:
    """Prefer the row with non-empty text; fill gaps from the other."""
    a_text = (a.get("text") or a.get("body") or "").strip()
    b_text = (b.get("text") or b.get("body") or "").strip()
    if b_text and (not a_text or len(b_text) > len(a_text)):
        base, other = dict(b), a
    else:
        base, other = dict(a), b
    for key in ("title", "source_ref", "url_or_local_path", "url", "language", "license"):
        if not base.get(key) and other.get(key):
            base[key] = other[key]
    if not (base.get("text") or base.get("body")):
        text = other.get("text") or other.get("body")
        if text:
            base["text"] = text
    meta = dict(base.get("metadata") or {})
    for k, v in (other.get("metadata") or {}).items():
        if k not in meta:
            meta[k] = v
    base["metadata"] = meta
    return base


def build_documents_from_sources(
    pkg: Package,
    *,
    only_referenced: bool = True,
) -> Package:
    """Auto-build ``documents[]`` from source excerpts (engine 0.1.15+ fields).

    Adapters set ``observation.document_id`` equal to ``source.ref``. This helper
    materializes a ``documents[]`` row per referenced id using the source's
    title / excerpt / url / license so import and Data Explorer get full
    document rows (not just stubs).

    Existing ``documents[]`` rows are preserved; gaps (empty text/title) may be
    filled from the matching source. Returns a shallow-copied package.
    """
    out = dict(pkg)
    sources = list(out.get("sources") or [])
    observations = list(out.get("observations") or [])
    sources_by_ref: Dict[str, dict] = {
        s.get("ref"): s for s in sources if isinstance(s, dict) and s.get("ref")
    }

    existing: Dict[str, dict] = {}
    for d in out.get("documents") or []:
        if not isinstance(d, dict):
            continue
        did = (d.get("document_id") or d.get("id") or "").strip()
        if did:
            existing[did] = dict(d)

    referenced: set = set()
    for o in observations:
        if not isinstance(o, dict):
            continue
        did = (o.get("document_id") or "").strip()
        if not did:
            did = ((o.get("metadata") or {}).get("document_id") or "").strip()
        if did:
            referenced.add(did)

    if only_referenced:
        candidates = referenced
    else:
        candidates = set(sources_by_ref.keys()) | referenced

    docs = dict(existing)
    for did in sorted(candidates):
        src = sources_by_ref.get(did)
        if src is None:
            # document_id may not equal source.ref — keep existing only
            continue
        text = (src.get("excerpt") or src.get("text") or src.get("body") or "").strip()
        title = (src.get("title") or "").strip()
        url = src.get("url_or_local_path") or src.get("url") or ""
        language = src.get("language") or "en"
        license_s = (
            src.get("license")
            or (src.get("metadata") or {}).get("license")
            or ""
        )
        if isinstance(license_s, str):
            license_s = license_s.strip()
        else:
            license_s = ""

        if did in docs:
            cur = docs[did]
            if not (cur.get("text") or cur.get("body")) and text:
                cur["text"] = text
            if not (cur.get("title") or "").strip() and title:
                cur["title"] = title
            if not cur.get("source_ref"):
                cur["source_ref"] = did
            if not (cur.get("url_or_local_path") or cur.get("url")) and url:
                cur["url_or_local_path"] = url
            if not (cur.get("license") or "").strip() and license_s:
                cur["license"] = license_s
            if not cur.get("language"):
                cur["language"] = language
            continue

        # Skip empty shells when there is nothing useful to store
        if not text and not title and not url:
            continue

        docs[did] = {
            "document_id": did,
            "source_ref": did,
            "title": title,
            "text": text,
            "url_or_local_path": url,
            "language": language,
            "license": license_s,
            "metadata": {
                "auto_built": True,
                "from": "source_excerpt",
            },
        }

    if docs:
        out["documents"] = [docs[k] for k in sorted(docs.keys())]
    return out


def ensure_documents(pkg: Package, **kwargs: Any) -> Package:
    """Ensure package has ``documents[]`` and auto-aligned ``char_span`` when useful."""
    out = build_documents_from_sources(pkg, **kwargs)
    return align_observation_char_spans(out)


def merge_packages(packages: Iterable[Package]) -> Package:
    """Union entities (by type+name), concat sources/observations/documents.

    Source ``ref`` collisions: later package wins for that ref (last-write),
    and observations that pointed at the replaced ref still use the same key.
    Documents merge by ``document_id`` (prefer non-empty text).
    """
    entities: Dict[tuple, dict] = {}
    sources_by_ref: Dict[str, dict] = {}
    sources_no_ref: List[dict] = []
    observations: List[dict] = []
    documents_by_id: Dict[str, dict] = {}

    for pkg in packages:
        clean = strip_package(pkg)
        for ent in clean["entities"]:
            key = _entity_key(ent)
            if key in entities:
                entities[key] = _merge_entity(entities[key], ent)
            else:
                entities[key] = dict(ent)
        for src in clean["sources"]:
            ref = src.get("ref")
            if ref:
                sources_by_ref[ref] = dict(src)
            else:
                sources_no_ref.append(dict(src))
        observations.extend(dict(o) for o in clean["observations"])
        for d in clean.get("documents") or []:
            if not isinstance(d, dict):
                continue
            did = (d.get("document_id") or d.get("id") or "").strip()
            if not did:
                continue
            if did in documents_by_id:
                documents_by_id[did] = _merge_document(documents_by_id[did], d)
            else:
                documents_by_id[did] = dict(d)

    merged: Package = {
        "entities": list(entities.values()),
        "sources": list(sources_by_ref.values()) + sources_no_ref,
        "observations": observations,
    }
    if documents_by_id:
        merged["documents"] = [documents_by_id[k] for k in sorted(documents_by_id.keys())]
    # Fill any missing docs from source excerpts after merge
    return ensure_documents(merged)


def package_stats(pkg: Package) -> dict:
    clean = strip_package(pkg)
    refs = {s.get("ref") for s in clean["sources"] if s.get("ref")}
    orphan_obs = [
        o for o in clean["observations"] if o.get("source_ref") not in refs
    ]
    docs = clean.get("documents") or []
    docs_with_text = sum(
        1 for d in docs
        if isinstance(d, dict) and (d.get("text") or d.get("body") or "").strip()
    )
    obs_with_span = sum(
        1 for o in clean["observations"]
        if isinstance(o, dict) and o.get("char_span") not in (None, "")
    )
    return {
        "entities": len(clean["entities"]),
        "sources": len(clean["sources"]),
        "observations": len(clean["observations"]),
        "documents": len(docs),
        "documents_with_text": docs_with_text,
        "observations_with_char_span": obs_with_span,
        "orphan_observations": len(orphan_obs),
        "source_refs": len(refs),
    }

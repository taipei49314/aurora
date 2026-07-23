"""Helpers for composing AURORA import packages."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


Package = Dict[str, Any]


def strip_package(raw: dict) -> Package:
    """Keep only the three arrays the engine accepts."""
    return {
        "entities": list(raw.get("entities") or []),
        "sources": list(raw.get("sources") or []),
        "observations": list(raw.get("observations") or []),
    }


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


def merge_packages(packages: Iterable[Package]) -> Package:
    """Union entities (by type+name), concat sources/observations.

    Source ``ref`` collisions: later package wins for that ref (last-write),
    and observations that pointed at the replaced ref still use the same key.
    """
    entities: Dict[tuple, dict] = {}
    sources_by_ref: Dict[str, dict] = {}
    sources_no_ref: List[dict] = []
    observations: List[dict] = []

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

    return {
        "entities": list(entities.values()),
        "sources": list(sources_by_ref.values()) + sources_no_ref,
        "observations": observations,
    }


def package_stats(pkg: Package) -> dict:
    clean = strip_package(pkg)
    refs = {s.get("ref") for s in clean["sources"] if s.get("ref")}
    orphan_obs = [
        o for o in clean["observations"] if o.get("source_ref") not in refs
    ]
    return {
        "entities": len(clean["entities"]),
        "sources": len(clean["sources"]),
        "observations": len(clean["observations"]),
        "orphan_observations": len(orphan_obs),
        "source_refs": len(refs),
    }

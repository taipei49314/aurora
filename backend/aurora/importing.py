"""Import pipeline (spec §7).

Raw package -> Schema Validation -> Canonicalization -> Entity Resolution ->
Source Dedup -> Temporal Validation -> Observation Extraction -> Snapshot.

Determinism & idempotency: every id is content-derived, so re-importing the same
package produces the same ids and dedupes to the same snapshot — importing twice
never doubles the evidence (spec §34.3).

Entities that share an ``external_ids`` key are merged into the first entity
that claimed that key (aliases + external_ids union). Observations may resolve
subjects via name, ``ext:system:id``, or ``{name, external_ids}``.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .ids import prefixed_id, content_hash, normalize_text
from .models import Source, Entity, Observation, SOURCE_TYPES, ENTITY_TYPES, OBSERVATION_TYPES
from .errors import RowError
from .entity_resolution import (
    EntityResolver,
    normalize_external_id,
    normalize_external_ids,
    parse_entity_ref,
)
from .dedup import resolve_independence
from .store import make_snapshot

_REQUIRED_ENTITY = {"entity_type", "canonical_name"}
_REQUIRED_SOURCE = {"source_type", "publisher", "title"}
_REQUIRED_OBS = {"source_ref", "observation_type", "subject"}


def _extract_family_id(row: dict, meta: dict) -> str:
    """First-class family_id with metadata fallback (engine 0.1.8+)."""
    return (row.get("family_id") or meta.get("family_id") or "").strip()


def _derive_independence_group(row: dict, meta: dict, family_id: str = "") -> str:
    """When independence_group is empty, derive from wire/domain/family metadata."""
    wire = (meta.get("wire_id") or row.get("wire_id") or "").strip()
    if wire:
        return f"wire:{wire}"
    domain = (meta.get("outlet_domain") or row.get("outlet_domain") or "").strip()
    if domain:
        return f"domain:{domain}"
    family = (family_id or meta.get("family_id") or row.get("family_id") or "").strip()
    if family:
        return f"family:{family}"
    return ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _valid_date(d) -> bool:
    if d in (None, ""):
        return True
    try:
        date.fromisoformat(str(d)[:10])
        return True
    except ValueError:
        return False


def _merge_entity_row(existing: Entity, *, aliases, description, country, ext_ids, meta) -> None:
    for a in aliases or []:
        if a not in existing.aliases:
            existing.aliases.append(a)
    if description and not existing.description:
        existing.description = description
    if country and not existing.country:
        existing.country = country
    seen_norm = set(normalize_external_ids(existing.external_ids))
    for x in ext_ids or []:
        nk = normalize_external_id(x)
        if nk and nk not in seen_norm:
            existing.external_ids.append({"system": nk[0], "id": nk[1]})
            seen_norm.add(nk)
    for k, v in (meta or {}).items():
        if k not in existing.metadata:
            existing.metadata[k] = v


def import_package(raw: dict, *, created_at: str | None = None) -> "Snapshot":
    created_at = created_at or _now()
    errors: list[RowError] = []

    # --- 1. build entities (deterministic ids; merge on shared external_ids) ---
    entities: dict[str, Entity] = {}
    ext_owner: Dict[Tuple[str, str], str] = {}  # (system,id) -> entity_id

    for i, row in enumerate(raw.get("entities", [])):
        missing = _REQUIRED_ENTITY - set(k for k, v in row.items() if v not in (None, ""))
        if missing:
            errors.append(RowError(i, ",".join(sorted(missing)), "SCHEMA_VALIDATION_FAILED",
                                   "missing required entity fields", str(row)))
            continue
        if row["entity_type"] not in ENTITY_TYPES:
            errors.append(RowError(i, "entity_type", "SCHEMA_VALIDATION_FAILED",
                                   f"unknown entity_type {row['entity_type']}", str(row["entity_type"])))
            continue
        meta = dict(row.get("metadata") or {})
        ext_ids_raw = list(row.get("external_ids") or meta.pop("external_ids", None) or [])
        ext_keys = normalize_external_ids(ext_ids_raw)
        # normalize stored form
        ext_ids = [{"system": sys, "id": iid} for sys, iid in ext_keys]

        # Prefer merge into existing owner of any external id
        owner_eid = None
        for key in sorted(ext_keys):
            if key in ext_owner:
                owner_eid = ext_owner[key]
                break

        eid = prefixed_id("ent", row["entity_type"], normalize_text(row["canonical_name"]))
        aliases = list(row.get("aliases", []))
        description = row.get("description", "")
        country = row.get("country", "")

        if owner_eid and owner_eid in entities:
            existing = entities[owner_eid]
            # name may differ across dumps — keep owner id, add name as alias
            cname = row["canonical_name"]
            if normalize_text(cname) != normalize_text(existing.canonical_name):
                if cname not in existing.aliases:
                    existing.aliases.append(cname)
            _merge_entity_row(
                existing,
                aliases=aliases,
                description=description,
                country=country,
                ext_ids=ext_ids,
                meta=meta,
            )
            target = existing
        elif eid in entities:
            existing = entities[eid]
            _merge_entity_row(
                existing,
                aliases=aliases,
                description=description,
                country=country,
                ext_ids=ext_ids,
                meta=meta,
            )
            target = existing
        else:
            target = Entity(
                entity_id=eid,
                entity_type=row["entity_type"],
                canonical_name=row["canonical_name"],
                aliases=aliases,
                description=description,
                country=country,
                created_at=created_at,
                external_ids=ext_ids,
                metadata=meta,
            )
            entities[eid] = target

        # register external ownership; collide if two different eids claim same key
        for key in ext_keys:
            prev = ext_owner.get(key)
            if prev is None:
                ext_owner[key] = target.entity_id
            elif prev != target.entity_id:
                errors.append(RowError(
                    i, "external_ids", "EXTERNAL_ID_COLLISION",
                    f"external id {key[0]}:{key[1]} already owned by {prev}",
                    f"{key[0]}:{key[1]}",
                ))

    resolver = EntityResolver(entities.values())
    amb = resolver.ambiguities()
    for a in amb:
        errors.append(RowError(-1, "alias", "ENTITY_RESOLUTION_AMBIGUOUS",
                               f"name {a['name']} maps to {len(a['entity_ids'])} entities", a["name"]))
    for c in resolver.external_id_collisions():
        errors.append(RowError(
            -1, "external_ids", "EXTERNAL_ID_COLLISION",
            f"external id {c['system']}:{c['id']} maps to {len(c['entity_ids'])} entities",
            f"{c['system']}:{c['id']}",
        ))

    # --- 2. build sources (dedup by content hash) ---
    sources: dict[str, Source] = {}
    ref_to_sid: dict[str, str] = {}
    for i, row in enumerate(raw.get("sources", [])):
        missing = _REQUIRED_SOURCE - set(k for k, v in row.items() if v not in (None, ""))
        if missing:
            errors.append(RowError(i, ",".join(sorted(missing)), "SCHEMA_VALIDATION_FAILED",
                                   "missing required source fields", str(row)))
            continue
        if row["source_type"] not in SOURCE_TYPES:
            errors.append(RowError(i, "source_type", "SCHEMA_VALIDATION_FAILED",
                                   f"unknown source_type {row['source_type']}", str(row["source_type"])))
            continue
        if not _valid_date(row.get("published_at")):
            errors.append(RowError(i, "published_at", "SOURCE_DATE_MISSING",
                                   "unparseable published_at", str(row.get("published_at"))))
        chash = content_hash(row.get("source_type"), normalize_text(row["title"]),
                             normalize_text(row.get("excerpt", "")), row.get("publisher"))
        sid = prefixed_id("src", chash)
        if sid not in sources:
            meta = dict(row.get("metadata", {}))
            if "excerpt" in row:
                meta["excerpt"] = row["excerpt"]
            family_id = _extract_family_id(row, meta)
            # Prefer first-class field; drop duplicate from metadata when promoted
            if family_id and meta.get("family_id") == family_id:
                meta.pop("family_id", None)
            indep = (row.get("independence_group") or "").strip()
            if not indep:
                indep = _derive_independence_group(row, meta, family_id=family_id)
            sources[sid] = Source(
                source_id=sid, source_type=row["source_type"], publisher=row["publisher"],
                title=row["title"], published_at=(row.get("published_at") or None), retrieved_at=created_at,
                url_or_local_path=row.get("url_or_local_path", ""), content_hash=chash,
                independence_group=indep, reliability_tier=row.get("reliability_tier", "C"),
                language=row.get("language", "en"), family_id=family_id, metadata=meta,
            )
        if "ref" in row:
            ref_to_sid[row["ref"]] = sid

    indep = resolve_independence(list(sources.values()))
    resolved_group = indep["resolved_group"]

    # --- 3. build observations ---
    observations: dict[str, Observation] = {}
    for i, row in enumerate(raw.get("observations", [])):
        # subject may be dict — required check tolerates that
        if row.get("subject") in (None, ""):
            errors.append(RowError(i, "subject", "SCHEMA_VALIDATION_FAILED",
                                   "missing required observation fields", str(row)))
            continue
        missing = set()
        if not row.get("source_ref"):
            missing.add("source_ref")
        if not row.get("observation_type"):
            missing.add("observation_type")
        if missing:
            errors.append(RowError(i, ",".join(sorted(missing)), "SCHEMA_VALIDATION_FAILED",
                                   "missing required observation fields", str(row)))
            continue
        if row["observation_type"] not in OBSERVATION_TYPES:
            errors.append(RowError(i, "observation_type", "SCHEMA_VALIDATION_FAILED",
                                   f"unknown observation_type {row['observation_type']}", str(row["observation_type"])))
            continue
        sid = ref_to_sid.get(row["source_ref"])
        if sid is None:
            errors.append(RowError(i, "source_ref", "SCHEMA_VALIDATION_FAILED",
                                   f"observation references unknown source {row['source_ref']}", str(row["source_ref"])))
            continue

        meta = dict(row.get("metadata", {}))
        # optional observation-level external hints
        subj_ext = normalize_external_ids(
            row.get("subject_external_ids")
            or meta.pop("subject_external_ids", None)
            or ([meta["subject_external_id"]] if meta.get("subject_external_id") else None)
        )
        obj_ext = normalize_external_ids(
            row.get("object_external_ids")
            or meta.pop("object_external_ids", None)
            or ([meta["object_external_id"]] if meta.get("object_external_id") else None)
        )

        name_s, ext_s = parse_entity_ref(row["subject"])
        subj = resolver.resolve(name_s, external_ids=list(ext_s) + list(subj_ext))
        if subj is None:
            errors.append(RowError(i, "subject", "ENTITY_RESOLUTION_AMBIGUOUS",
                                   f"cannot resolve subject {row['subject']!r}", str(row["subject"])))
            continue

        obj = None
        if row.get("object") not in (None, ""):
            name_o, ext_o = parse_entity_ref(row["object"])
            obj = resolver.resolve(name_o, external_ids=list(ext_o) + list(obj_ext))
            if obj is None:
                errors.append(RowError(i, "object", "ENTITY_RESOLUTION_AMBIGUOUS",
                                       f"cannot resolve object {row['object']!r}", str(row["object"])))
                continue

        if not _valid_date(row.get("observed_at")):
            errors.append(RowError(i, "observed_at", "SOURCE_DATE_MISSING",
                                   "unparseable observed_at", str(row.get("observed_at"))))
        src = sources[sid]
        meta["source_type"] = src.source_type
        meta["independence_group"] = resolved_group.get(sid, sid)
        meta.setdefault("reliability_tier", src.reliability_tier or "C")
        oid = prefixed_id(
            "obs", sid, row["observation_type"], subj, obj or "",
            row.get("observed_at") or "",
            normalize_text(row.get("text_excerpt", "")),
        )
        if oid not in observations:
            observations[oid] = Observation(
                observation_id=oid, source_id=sid, observed_at=(row.get("observed_at") or None),
                observation_type=row["observation_type"], subject_entity=subj, object_entity=obj,
                numeric_value=row.get("numeric_value"), unit=row.get("unit"),
                text_excerpt=row.get("text_excerpt", ""), confidence=float(row.get("confidence", 0.7)),
                metadata=meta,
            )

    snap = make_snapshot(
        entities=sorted(entities.values(), key=lambda e: e.entity_id),
        sources=sorted(sources.values(), key=lambda s: s.source_id),
        observations=sorted(observations.values(), key=lambda o: o.observation_id),
        resolved_group=resolved_group,
        import_errors=[e.__dict__ for e in errors],
        created_at=created_at,
    )
    snap.counts.update({
        "raw_source_count": indep["raw_source_count"],
        "deduplicated_source_count": indep["deduplicated_source_count"],
        "independent_source_count": indep["independent_source_count"],
    })
    return snap

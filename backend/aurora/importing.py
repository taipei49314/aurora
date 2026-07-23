"""Import pipeline (spec §7).

Raw package -> Schema Validation -> Canonicalization -> Entity Resolution ->
Source Dedup -> Temporal Validation -> Observation Extraction -> Snapshot.

Determinism & idempotency: every id is content-derived, so re-importing the same
package produces the same ids and dedupes to the same snapshot — importing twice
never doubles the evidence (spec §34.3).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from .ids import prefixed_id, content_hash, normalize_text
from .models import Source, Entity, Observation, SOURCE_TYPES, ENTITY_TYPES, OBSERVATION_TYPES
from .errors import AuroraError, RowError
from .entity_resolution import EntityResolver
from .dedup import resolve_independence
from .store import make_snapshot

_REQUIRED_ENTITY = {"entity_type", "canonical_name"}
_REQUIRED_SOURCE = {"source_type", "publisher", "title"}
_REQUIRED_OBS = {"source_ref", "observation_type", "subject"}


def _derive_independence_group(row: dict, meta: dict) -> str:
    """When independence_group is empty, derive from wire/domain/family metadata.

    Does not invent groups from free-text publishers (too noisy). Explicit
    ``independence_group`` on the row always wins (caller should set it when known).
    """
    wire = (meta.get("wire_id") or row.get("wire_id") or "").strip()
    if wire:
        return f"wire:{wire}"
    domain = (meta.get("outlet_domain") or row.get("outlet_domain") or "").strip()
    if domain:
        return f"domain:{domain}"
    family = (meta.get("family_id") or row.get("family_id") or "").strip()
    if family:
        return f"family:{family}"
    return ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _valid_date(d) -> bool:
    if d in (None, ""):
        return True  # missing allowed but flagged
    try:
        date.fromisoformat(str(d)[:10])
        return True
    except ValueError:
        return False


def import_package(raw: dict, *, created_at: str | None = None) -> "Snapshot":
    created_at = created_at or _now()
    errors: list[RowError] = []

    # --- 1. build entities (deterministic ids) ---
    entities: dict[str, Entity] = {}
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
        eid = prefixed_id("ent", row["entity_type"], normalize_text(row["canonical_name"]))
        meta = dict(row.get("metadata") or {})
        # Prefer first-class external_ids; fall back to metadata.external_ids (v0 convention)
        ext_ids = list(row.get("external_ids") or meta.pop("external_ids", None) or [])
        if eid not in entities:
            entities[eid] = Entity(
                entity_id=eid, entity_type=row["entity_type"], canonical_name=row["canonical_name"],
                aliases=list(row.get("aliases", [])), description=row.get("description", ""),
                country=row.get("country", ""), created_at=created_at,
                external_ids=ext_ids, metadata=meta,
            )
        else:
            # merge aliases + external_ids on re-import (idempotent union)
            existing = entities[eid]
            for a in row.get("aliases", []):
                if a not in existing.aliases:
                    existing.aliases.append(a)
            seen = {
                (x.get("system"), x.get("id"))
                for x in (existing.external_ids or [])
                if isinstance(x, dict)
            }
            for x in ext_ids:
                if not isinstance(x, dict):
                    continue
                key = (x.get("system"), x.get("id"))
                if key not in seen:
                    existing.external_ids.append(x)
                    seen.add(key)

    resolver = EntityResolver(entities.values())
    amb = resolver.ambiguities()
    for a in amb:
        errors.append(RowError(-1, "alias", "ENTITY_RESOLUTION_AMBIGUOUS",
                               f"name {a['name']} maps to {len(a['entity_ids'])} entities", a["name"]))

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
            indep = (row.get("independence_group") or "").strip()
            if not indep:
                # Auto-derive from common adapter/metadata conventions (engine 0.1.1+)
                indep = _derive_independence_group(row, meta)
            sources[sid] = Source(
                source_id=sid, source_type=row["source_type"], publisher=row["publisher"],
                title=row["title"], published_at=(row.get("published_at") or None), retrieved_at=created_at,
                url_or_local_path=row.get("url_or_local_path", ""), content_hash=chash,
                independence_group=indep, reliability_tier=row.get("reliability_tier", "C"),
                language=row.get("language", "en"), metadata=meta,
            )
        # map the raw ref key (given by caller) to the resolved source id
        if "ref" in row:
            ref_to_sid[row["ref"]] = sid

    indep = resolve_independence(list(sources.values()))
    resolved_group = indep["resolved_group"]

    # --- 3. build observations (dedup by deterministic id) ---
    observations: dict[str, Observation] = {}
    for i, row in enumerate(raw.get("observations", [])):
        missing = _REQUIRED_OBS - set(k for k, v in row.items() if v not in (None, ""))
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
        subj = resolver.resolve(row["subject"])
        if subj is None:
            errors.append(RowError(i, "subject", "ENTITY_RESOLUTION_AMBIGUOUS",
                                   f"cannot resolve subject {row['subject']!r}", str(row["subject"])))
            continue
        obj = resolver.resolve(row["object"]) if row.get("object") else None
        if not _valid_date(row.get("observed_at")):
            errors.append(RowError(i, "observed_at", "SOURCE_DATE_MISSING",
                                   "unparseable observed_at", str(row.get("observed_at"))))
        src = sources[sid]
        meta = dict(row.get("metadata", {}))
        meta["source_type"] = src.source_type
        meta["independence_group"] = resolved_group.get(sid, sid)
        # Stamp tier so scoring/data-quality works even if source rows are later subset
        meta.setdefault("reliability_tier", src.reliability_tier or "C")
        oid = prefixed_id("obs", sid, row["observation_type"], subj, obj or "",
                          row.get("observed_at") or "", normalize_text(row.get("text_excerpt", "")))
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

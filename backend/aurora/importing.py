"""Import pipeline (spec §7).

Raw package -> Schema Validation -> Canonicalization -> Entity Resolution ->
Source Dedup -> Temporal Validation -> Observation Extraction -> Snapshot.

Determinism & idempotency: every id is content-derived, so re-importing the same
package produces the same ids and dedupes to the same snapshot — importing twice
never doubles the evidence (spec §34.3).

Entities that share an ``external_ids`` key are merged into the first entity
that claimed that key (aliases + external_ids union). Observations may resolve
subjects via name, ``ext:system:id``, or ``{name, external_ids}``. Surface-form
``subject_raw`` / ``object_raw`` are stored for provenance (engine 0.1.38+).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .ids import prefixed_id, content_hash, normalize_text
from .char_span import align_char_span
from .models import (
    Source,
    Entity,
    Observation,
    Document,
    SOURCE_TYPES,
    ENTITY_TYPES,
    OBSERVATION_TYPES,
)
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


def _extract_event_date(row: dict, meta: dict) -> Optional[str]:
    """First-class event_date (application/filing) with metadata fallback (0.1.10+)."""
    raw = row.get("event_date") if row.get("event_date") not in (None, "") else meta.get("event_date")
    if raw in (None, ""):
        return None
    return str(raw).strip()[:10] if str(raw).strip() else None


def _extract_event_id(row: dict, meta: dict) -> str:
    """First-class event_id with metadata fallback (engine 0.1.11+)."""
    return (row.get("event_id") or meta.get("event_id") or "").strip()


def _extract_outlet_domain(row: dict, meta: dict) -> str:
    """First-class outlet_domain with metadata fallback (engine 0.1.12+)."""
    return (row.get("outlet_domain") or meta.get("outlet_domain") or row.get("domain") or meta.get("domain") or "").strip()


def _extract_wire_id(row: dict, meta: dict) -> str:
    """First-class wire_id with metadata fallback (engine 0.1.12+)."""
    return (row.get("wire_id") or meta.get("wire_id") or "").strip()


def _extract_license(row: dict, meta: dict, default: str = "") -> str:
    """First-class license with metadata + package default fallback (engine 0.1.14+)."""
    return (row.get("license") or meta.get("license") or default or "").strip()


def _extract_document_id(row: dict, meta: dict) -> str:
    """First-class document_id with metadata fallback (engine 0.1.15+)."""
    return (row.get("document_id") or meta.get("document_id") or "").strip()


def _extract_mention_raw(row: dict, meta: dict, *, field: str, ref: Any) -> str:
    """First-class subject_raw / object_raw with metadata + derivation (0.1.38+).

    Prefer explicit top-level / metadata; otherwise derive a stable surface form
    from the subject/object ref (name string, structured name, or compact ext ref).
    """
    key = f"{field}_raw"
    explicit = row.get(key)
    if explicit in (None, ""):
        explicit = meta.get(key)
    if explicit not in (None, ""):
        return str(explicit).strip()
    return _derive_mention_raw(ref)


def _derive_mention_raw(ref: Any) -> str:
    """Surface form for a subject/object ref when no explicit *_raw is given."""
    if ref is None or ref == "":
        return ""
    if isinstance(ref, dict):
        name = ref.get("name") or ref.get("canonical_name") or ref.get("subject")
        if name not in (None, ""):
            return str(name).strip()
        # compact first external id for pure-id structured refs
        ext = normalize_external_ids(
            ref.get("external_ids")
            or ([ref["external_id"]] if ref.get("external_id") else None)
        )
        one = normalize_external_id(ref)
        if one and one not in ext:
            ext.append(one)
        if ext:
            sys, iid = ext[0]
            return f"ext:{sys}:{iid}"
        return ""
    if isinstance(ref, str):
        return ref.strip()
    return str(ref).strip()


def _extract_char_span(row: dict, meta: dict) -> Optional[list]:
    """First-class char_span [start, end] with metadata fallback (engine 0.1.15+)."""
    raw = row.get("char_span") if row.get("char_span") not in (None, "") else meta.get("char_span")
    if raw in (None, ""):
        return None
    if isinstance(raw, dict):
        start, end = raw.get("start"), raw.get("end")
        if start is None or end is None:
            return None
        try:
            a, b = int(start), int(end)
        except (TypeError, ValueError):
            return None
        return [a, b] if a <= b else [b, a]
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        try:
            a, b = int(raw[0]), int(raw[1])
        except (TypeError, ValueError):
            return None
        return [a, b] if a <= b else [b, a]
    return None


def _normalize_geo(raw) -> dict:
    """Normalize location/geo payloads into a stable dict of known keys."""
    if raw in (None, "", {}):
        return {}
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return {}
        if len(s) in (2, 3) and s.isalpha():
            return {"country": s.upper()}
        return {"raw": s}
    if not isinstance(raw, dict):
        return {}
    out: dict = {}
    for k in ("country", "region", "city", "raw", "jurisdiction", "admin1", "state"):
        v = raw.get(k)
        if v in (None, ""):
            continue
        key = "region" if k in ("admin1", "state") else k
        val = str(v).strip()
        if key == "country" and len(val) in (2, 3) and val.isalpha():
            val = val.upper()
        if key not in out:
            out[key] = val
    return out


def _extract_geo(row: dict, meta: dict) -> dict:
    """First-class geo with location/country/jurisdiction fallbacks (engine 0.1.13+)."""
    g = _normalize_geo(row.get("geo"))
    if not g:
        g = _normalize_geo(row.get("location") or meta.get("geo") or meta.get("location"))
    country = (row.get("country") or meta.get("country") or "").strip()
    jurisdiction = (row.get("jurisdiction") or meta.get("jurisdiction") or "").strip()
    if country or jurisdiction:
        g = dict(g)
        if country and not g.get("country"):
            g["country"] = country.upper() if len(country) in (2, 3) and country.isalpha() else country
        if jurisdiction and not g.get("jurisdiction"):
            g["jurisdiction"] = jurisdiction
    return g


def _derive_independence_group(
    row: dict,
    meta: dict,
    family_id: str = "",
    event_id: str = "",
    wire_id: str = "",
    outlet_domain: str = "",
) -> str:
    """When independence_group is empty, derive from wire/domain/family/event fields."""
    wire = (wire_id or meta.get("wire_id") or row.get("wire_id") or "").strip()
    if wire:
        return f"wire:{wire}"
    domain = (outlet_domain or meta.get("outlet_domain") or row.get("outlet_domain") or "").strip()
    if domain:
        return f"domain:{domain}"
    family = (family_id or meta.get("family_id") or row.get("family_id") or "").strip()
    if family:
        return f"family:{family}"
    event = (event_id or meta.get("event_id") or row.get("event_id") or "").strip()
    if event:
        return f"event:{event}"
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

    # Optional package-level default license for public corpora (0.1.14+)
    package_license = (raw.get("license") or "").strip()
    if not package_license and isinstance(raw.get("package"), dict):
        package_license = (raw["package"].get("license") or "").strip()
    if not package_license and isinstance(raw.get("meta"), dict):
        package_license = (raw["meta"].get("license") or "").strip()

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
        # Validate top-level or nested event_date early
        meta_probe = dict(row.get("metadata") or {})
        event_probe = row.get("event_date") if row.get("event_date") not in (None, "") else meta_probe.get("event_date")
        if not _valid_date(event_probe):
            errors.append(RowError(i, "event_date", "SOURCE_DATE_MISSING",
                                   "unparseable event_date", str(event_probe)))
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
            event_date = _extract_event_date(row, meta)
            if event_date and str(meta.get("event_date") or "")[:10] == event_date:
                meta.pop("event_date", None)
            event_id = _extract_event_id(row, meta)
            if event_id and meta.get("event_id") == event_id:
                meta.pop("event_id", None)
            outlet_domain = _extract_outlet_domain(row, meta)
            if outlet_domain and meta.get("outlet_domain") == outlet_domain:
                meta.pop("outlet_domain", None)
            # also drop alias key when promoted
            if outlet_domain and meta.get("domain") == outlet_domain:
                meta.pop("domain", None)
            wire_id = _extract_wire_id(row, meta)
            if wire_id and meta.get("wire_id") == wire_id:
                meta.pop("wire_id", None)
            geo = _extract_geo(row, meta)
            if geo:
                # promote out of metadata once first-class
                meta.pop("geo", None)
                meta.pop("location", None)
                meta.pop("country", None)
                meta.pop("jurisdiction", None)
            license_s = _extract_license(row, meta, default=package_license)
            if license_s:
                meta.pop("license", None)
            indep = (row.get("independence_group") or "").strip()
            if not indep:
                indep = _derive_independence_group(
                    row,
                    meta,
                    family_id=family_id,
                    event_id=event_id,
                    wire_id=wire_id,
                    outlet_domain=outlet_domain,
                )
            sources[sid] = Source(
                source_id=sid, source_type=row["source_type"], publisher=row["publisher"],
                title=row["title"], published_at=(row.get("published_at") or None), retrieved_at=created_at,
                url_or_local_path=row.get("url_or_local_path", ""), content_hash=chash,
                independence_group=indep, reliability_tier=row.get("reliability_tier", "C"),
                language=row.get("language", "en"), family_id=family_id,
                event_date=event_date, event_id=event_id,
                outlet_domain=outlet_domain, wire_id=wire_id, geo=geo,
                license=license_s, metadata=meta,
            )
        if "ref" in row:
            ref_to_sid[row["ref"]] = sid

    indep = resolve_independence(list(sources.values()))
    resolved_group = indep["resolved_group"]

    # --- 3. build observations ---
    observations: dict[str, Observation] = {}
    for i, row in enumerate(raw.get("observations", [])):
        meta = dict(row.get("metadata", {}))
        # subject may be dict; subject_raw alone is accepted as staging fallback (0.1.38+)
        subject_ref = row.get("subject")
        if subject_ref in (None, ""):
            subject_ref = row.get("subject_raw") or meta.get("subject_raw") or ""
        if subject_ref in (None, ""):
            errors.append(RowError(i, "subject", "SCHEMA_VALIDATION_FAILED",
                                   "missing required observation fields (subject or subject_raw)", str(row)))
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

        subject_raw = _extract_mention_raw(row, meta, field="subject", ref=subject_ref)
        if subject_raw:
            meta.pop("subject_raw", None)

        name_s, ext_s = parse_entity_ref(subject_ref)
        subj = resolver.resolve(name_s, external_ids=list(ext_s) + list(subj_ext))
        if subj is None:
            errors.append(RowError(
                i, "subject", "ENTITY_RESOLUTION_AMBIGUOUS",
                f"cannot resolve subject {subject_ref!r}"
                + (f" (subject_raw={subject_raw!r})" if subject_raw else ""),
                subject_raw or str(subject_ref),
            ))
            continue

        obj = None
        object_ref = row.get("object")
        if object_ref in (None, ""):
            object_ref = row.get("object_raw") or meta.get("object_raw") or None
        object_raw = ""
        if object_ref not in (None, ""):
            object_raw = _extract_mention_raw(row, meta, field="object", ref=object_ref)
            if object_raw:
                meta.pop("object_raw", None)
            name_o, ext_o = parse_entity_ref(object_ref)
            obj = resolver.resolve(name_o, external_ids=list(ext_o) + list(obj_ext))
            if obj is None:
                errors.append(RowError(
                    i, "object", "ENTITY_RESOLUTION_AMBIGUOUS",
                    f"cannot resolve object {object_ref!r}"
                    + (f" (object_raw={object_raw!r})" if object_raw else ""),
                    object_raw or str(object_ref),
                ))
                continue

        if not _valid_date(row.get("observed_at")):
            errors.append(RowError(i, "observed_at", "SOURCE_DATE_MISSING",
                                   "unparseable observed_at", str(row.get("observed_at"))))
        src = sources[sid]
        # Dual-date fallback (0.1.10+): empty observed_at → source.event_date → published_at
        observed_at = row.get("observed_at") or None
        if observed_at in (None, ""):
            observed_at = src.event_date or src.published_at or None
        # First-class event_id (0.1.11+): top-level / metadata / inherit from source
        event_id = _extract_event_id(row, meta) or (src.event_id or "")
        if event_id and meta.get("event_id") == event_id:
            meta.pop("event_id", None)
        # First-class geo (0.1.13+): start from source, overlay observation fields
        geo = dict(src.geo or {})
        obs_geo = _extract_geo(row, meta)
        if obs_geo:
            geo.update(obs_geo)
        if geo:
            meta.pop("geo", None)
            meta.pop("location", None)
            meta.pop("country", None)
            meta.pop("jurisdiction", None)
        # Document provenance (0.1.15+): document_id + optional char_span
        document_id = _extract_document_id(row, meta)
        if document_id:
            meta.pop("document_id", None)
        char_span = _extract_char_span(row, meta)
        if char_span is not None:
            meta.pop("char_span", None)
        meta["source_type"] = src.source_type
        meta["independence_group"] = resolved_group.get(sid, sid)
        meta.setdefault("reliability_tier", src.reliability_tier or "C")
        oid = prefixed_id(
            "obs", sid, row["observation_type"], subj, obj or "",
            observed_at or "",
            normalize_text(row.get("text_excerpt", "")),
        )
        if oid not in observations:
            observations[oid] = Observation(
                observation_id=oid, source_id=sid, observed_at=observed_at,
                observation_type=row["observation_type"], subject_entity=subj, object_entity=obj,
                numeric_value=row.get("numeric_value"), unit=row.get("unit"),
                text_excerpt=row.get("text_excerpt", ""), confidence=float(row.get("confidence", 0.7)),
                event_id=event_id, geo=geo, document_id=document_id,
                char_span=char_span, subject_raw=subject_raw, object_raw=object_raw,
                metadata=meta,
            )

    # Optional documents[] for full-text / path provenance (engine 0.1.15+)
    documents: dict[str, Document] = {}
    for i, row in enumerate(raw.get("documents") or []):
        if not isinstance(row, dict):
            errors.append(RowError(i, "documents", "SCHEMA_VALIDATION_FAILED",
                                   "document row must be an object", str(row)))
            continue
        did = (row.get("document_id") or row.get("id") or "").strip()
        if not did:
            errors.append(RowError(i, "document_id", "SCHEMA_VALIDATION_FAILED",
                                   "missing document_id", str(row)))
            continue
        src_ref = (row.get("source_ref") or "").strip()
        source_id = ref_to_sid.get(src_ref, "") if src_ref else ""
        if src_ref and not source_id:
            errors.append(RowError(i, "source_ref", "SCHEMA_VALIDATION_FAILED",
                                   f"document references unknown source {src_ref}", src_ref))
        dmeta = dict(row.get("metadata") or {})
        documents[did] = Document(
            document_id=did,
            source_id=source_id,
            title=(row.get("title") or "").strip(),
            text=row.get("text") or row.get("body") or "",
            url_or_local_path=row.get("url_or_local_path") or row.get("url") or "",
            language=row.get("language") or "en",
            license=(row.get("license") or dmeta.pop("license", "") or "").strip(),
            metadata=dmeta,
        )

    # Auto-align char_span from text_excerpt when missing (engine 0.1.20+)
    auto_span_count = _auto_align_observation_spans(observations, documents)

    snap = make_snapshot(
        entities=sorted(entities.values(), key=lambda e: e.entity_id),
        sources=sorted(sources.values(), key=lambda s: s.source_id),
        observations=sorted(observations.values(), key=lambda o: o.observation_id),
        resolved_group=resolved_group,
        import_errors=[e.__dict__ for e in errors],
        created_at=created_at,
        documents=sorted(documents.values(), key=lambda d: d.document_id),
    )
    snap.counts.update({
        "raw_source_count": indep["raw_source_count"],
        "deduplicated_source_count": indep["deduplicated_source_count"],
        "independent_source_count": indep["independent_source_count"],
        "char_spans_auto_aligned": auto_span_count,
    })
    return snap


def _auto_align_observation_spans(
    observations: dict,
    documents: dict,
) -> int:
    """Fill missing Observation.char_span by locating text_excerpt in document text.

    Does not overwrite an existing char_span. Returns count of newly aligned rows.
    """
    if not documents or not observations:
        return 0
    n = 0
    for obs in observations.values():
        if getattr(obs, "char_span", None) is not None:
            continue
        did = (getattr(obs, "document_id", None) or "").strip()
        if not did:
            continue
        doc = documents.get(did)
        if doc is None:
            continue
        text = getattr(doc, "text", None) or ""
        excerpt = getattr(obs, "text_excerpt", None) or ""
        span = align_char_span(text, excerpt)
        if span is None:
            continue
        obs.char_span = span
        meta = dict(getattr(obs, "metadata", None) or {})
        meta["char_span_auto"] = True
        obs.metadata = meta
        n += 1
    return n

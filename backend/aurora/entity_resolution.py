"""Entity resolution (spec §6, §7).

Raw imports reference entities by *name string* (as they appear in a source)
and/or by **external_ids** (stable cross-dump keys such as LEI, CIK, domain).

Resolution order for ``resolve_ref``:

1. Explicit external id(s) if provided (and unique)
2. Compact ``ext:<system>:<id>`` form in the ref string
3. Normalized canonical name / alias
4. If the name is ambiguous, external ids (if any) disambiguate; otherwise
   ambiguity is reported (not silently guessed)

Determinism: maps are built in sorted entity-id order; ties break on smallest id
only when strict=False and a single remaining candidate remains after filters.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, List, Optional, Sequence, Tuple, Union

from .errors import AuroraError
from .ids import normalize_text

ExtKey = Tuple[str, str]  # (system, id)


def normalize_external_id(item: Any) -> Optional[ExtKey]:
    """Accept {system,id}, (system,id), or 'ext:system:id' / 'system:id' (single colon)."""
    if item is None or item == "":
        return None
    if isinstance(item, (tuple, list)) and len(item) == 2:
        sys, iid = str(item[0]).strip(), str(item[1]).strip()
        if sys and iid:
            return (sys, iid)
        return None
    if isinstance(item, dict):
        sys = str(item.get("system") or item.get("sys") or "").strip()
        iid = str(item.get("id") or item.get("value") or "").strip()
        if sys and iid:
            return (sys, iid)
        return None
    if isinstance(item, str):
        s = item.strip()
        if s.lower().startswith("ext:"):
            rest = s[4:]
            if ":" not in rest:
                return None
            sys, iid = rest.split(":", 1)
            sys, iid = sys.strip(), iid.strip()
            if sys and iid:
                return (sys, iid)
            return None
        # bare system:id — only when exactly one colon (avoid URLs)
        if s.count(":") == 1:
            sys, iid = s.split(":", 1)
            sys, iid = sys.strip(), iid.strip()
            if sys and iid and "://" not in s:
                return (sys, iid)
    return None


def normalize_external_ids(items: Optional[Iterable[Any]]) -> List[ExtKey]:
    out: List[ExtKey] = []
    seen = set()
    for it in items or []:
        key = normalize_external_id(it)
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def parse_entity_ref(ref: Any) -> Tuple[Optional[str], List[ExtKey]]:
    """Parse observation subject/object: string name, ext ref, or {name, external_ids}."""
    if ref is None or ref == "":
        return None, []
    if isinstance(ref, dict):
        name = ref.get("name") or ref.get("canonical_name") or ref.get("subject")
        name = str(name).strip() if name not in (None, "") else None
        ext = normalize_external_ids(
            ref.get("external_ids")
            or ([ref["external_id"]] if ref.get("external_id") else None)
        )
        # also allow system/id at top level
        one = normalize_external_id(ref)
        if one and one not in ext:
            ext.append(one)
        return name, ext
    if isinstance(ref, str):
        ext_one = normalize_external_id(ref)
        if ext_one and (
            ref.strip().lower().startswith("ext:")
            or (ref.count(":") == 1 and "://" not in ref)
        ):
            # pure external ref — name optional
            return None, [ext_one]
        return ref.strip(), []
    return str(ref), []


class EntityResolver:
    def __init__(self, entities):
        self.entities = {e.entity_id: e for e in entities}
        self._name_to_ids: dict[str, set[str]] = defaultdict(set)
        self._ext_to_ids: dict[ExtKey, set[str]] = defaultdict(set)
        for e in sorted(entities, key=lambda x: x.entity_id):
            self._index_entity(e)

    def _index_entity(self, e) -> None:
        self._name_to_ids[normalize_text(e.canonical_name)].add(e.entity_id)
        for alias in e.aliases or []:
            self._name_to_ids[normalize_text(alias)].add(e.entity_id)
        for raw in e.external_ids or []:
            key = normalize_external_id(raw)
            if key:
                self._ext_to_ids[key].add(e.entity_id)

    def register(self, entity) -> None:
        """Index a newly staged entity (provisional import; engine 0.1.39+)."""
        self.entities[entity.entity_id] = entity
        self._index_entity(entity)

    def name_is_ambiguous(self, name: Optional[str]) -> bool:
        """True when the normalized name maps to more than one known entity."""
        if not name or not str(name).strip():
            return False
        ids = self._name_to_ids.get(normalize_text(name)) or set()
        return len(ids) > 1

    def external_id_collisions(self) -> list[dict]:
        """External ids that map to more than one entity."""
        out = []
        for key, ids in sorted(self._ext_to_ids.items()):
            if len(ids) > 1:
                out.append({
                    "system": key[0],
                    "id": key[1],
                    "entity_ids": sorted(ids),
                })
        return out

    def ambiguities(self) -> list[dict]:
        """Names that resolve to more than one entity (spec error
        ENTITY_RESOLUTION_AMBIGUOUS)."""
        out = []
        for name, ids in sorted(self._name_to_ids.items()):
            if len(ids) > 1:
                out.append({"name": name, "entity_ids": sorted(ids)})
        return out

    def resolve_external(
        self,
        external_ids: Sequence[Any],
        *,
        strict: bool = False,
    ) -> Optional[str]:
        """Resolve via external ids. First unique match wins (sorted key order)."""
        keys = normalize_external_ids(external_ids)
        if not keys:
            return None
        candidates: set[str] = set()
        matched_any = False
        for key in sorted(keys):
            ids = self._ext_to_ids.get(key)
            if not ids:
                continue
            matched_any = True
            if not candidates:
                candidates = set(ids)
            else:
                candidates &= set(ids)
        if not matched_any:
            return None
        if len(candidates) == 1:
            return next(iter(candidates))
        if len(candidates) > 1:
            if strict:
                raise AuroraError(
                    "ENTITY_RESOLUTION_AMBIGUOUS",
                    f"external_ids {keys!r} resolve to {len(candidates)} entities",
                    stage="entity_resolution",
                    entity_ids=sorted(candidates),
                )
            return None
        return None

    def resolve(
        self,
        name: Optional[str],
        *,
        external_ids: Optional[Sequence[Any]] = None,
        strict: bool = False,
    ) -> Optional[str]:
        """Resolve by name and/or external_ids (see module docstring)."""
        ext_keys = normalize_external_ids(external_ids)
        # 1) pure external if no name
        if not name or not str(name).strip():
            return self.resolve_external(ext_keys, strict=strict)

        # 2) name looks like ext ref
        as_ext = normalize_external_id(name)
        if as_ext and (
            str(name).strip().lower().startswith("ext:")
            or (str(name).count(":") == 1 and "://" not in str(name))
        ):
            hit = self.resolve_external([as_ext] + list(ext_keys), strict=strict)
            if hit is not None:
                return hit

        key = normalize_text(name)
        ids = set(self._name_to_ids.get(key) or [])

        if not ids:
            # name unknown — fall back to external only
            return self.resolve_external(ext_keys, strict=strict)

        if len(ids) == 1:
            only = next(iter(ids))
            # if external_ids provided and disagree, prefer external when unique
            if ext_keys:
                by_ext = self.resolve_external(ext_keys, strict=False)
                if by_ext is not None and by_ext != only:
                    # external wins when it uniquely points elsewhere (rename/crosswalk)
                    return by_ext
            return only

        # ambiguous name — try external disambiguation
        if ext_keys:
            by_ext = self.resolve_external(ext_keys, strict=strict)
            if by_ext is not None:
                if by_ext in ids or True:
                    # prefer external even if not in name set (crosswalk rename)
                    return by_ext
            # filter name candidates by any matching external
            filtered = set()
            for eid in ids:
                ent = self.entities[eid]
                ent_keys = set(normalize_external_ids(ent.external_ids))
                if ent_keys & set(ext_keys):
                    filtered.add(eid)
            if len(filtered) == 1:
                return next(iter(filtered))

        if strict:
            raise AuroraError(
                "ENTITY_RESOLUTION_AMBIGUOUS",
                f"name {name!r} resolves to {len(ids)} entities",
                stage="entity_resolution",
                entity_ids=sorted(ids),
            )
        return None

    def resolve_ref(self, ref: Any, *, strict: bool = False) -> Optional[str]:
        """Resolve a subject/object field (string or structured object)."""
        name, ext = parse_entity_ref(ref)
        return self.resolve(name, external_ids=ext, strict=strict)

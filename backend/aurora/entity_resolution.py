"""Entity resolution (spec §6, §7).

Raw imports reference entities by *name string* (as they appear in a source).
Resolution maps every such mention to a canonical ``entity_id`` using declared
aliases, handling company renames (an old name is an alias of the current
entity) and flagging genuine ambiguity rather than guessing.

Determinism: alias maps are built in sorted order and ambiguity is reported, not
silently resolved to the first match.
"""
from __future__ import annotations

from collections import defaultdict

from .errors import AuroraError
from .ids import normalize_text


class EntityResolver:
    def __init__(self, entities):
        self.entities = {e.entity_id: e for e in entities}
        self._name_to_ids: dict[str, set[str]] = defaultdict(set)
        for e in sorted(entities, key=lambda x: x.entity_id):
            self._name_to_ids[normalize_text(e.canonical_name)].add(e.entity_id)
            for alias in e.aliases:
                self._name_to_ids[normalize_text(alias)].add(e.entity_id)

    def ambiguities(self) -> list[dict]:
        """Names that resolve to more than one entity (spec error
        ENTITY_RESOLUTION_AMBIGUOUS)."""
        out = []
        for name, ids in sorted(self._name_to_ids.items()):
            if len(ids) > 1:
                out.append({"name": name, "entity_ids": sorted(ids)})
        return out

    def resolve(self, name: str, *, strict: bool = False) -> str | None:
        key = normalize_text(name)
        ids = self._name_to_ids.get(key)
        if not ids:
            return None
        if len(ids) > 1:
            if strict:
                raise AuroraError(
                    "ENTITY_RESOLUTION_AMBIGUOUS",
                    f"name {name!r} resolves to {len(ids)} entities",
                    stage="entity_resolution",
                    entity_ids=sorted(ids),
                )
            return None
        return next(iter(ids))

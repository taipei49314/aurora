"""Entity resolution: aliases, renames, ambiguity."""
from __future__ import annotations

import pytest as _pytest
pytestmark = _pytest.mark.unit

from aurora.entity_resolution import EntityResolver
from aurora.models import Entity
from aurora.errors import AuroraError
import pytest


def _ent(eid, name, aliases=None):
    return Entity(entity_id=eid, entity_type="COMPANY", canonical_name=name, aliases=aliases or [])


def test_alias_resolves_to_canonical():
    r = EntityResolver([_ent("e1", "Monolith Corp", ["Monolith Corporation", "MonolithCorp"])])
    assert r.resolve("Monolith Corporation") == "e1"
    assert r.resolve("monolithcorp") == "e1"


def test_unknown_name_returns_none():
    r = EntityResolver([_ent("e1", "Acme")])
    assert r.resolve("Nonexistent") is None


def test_ambiguous_alias_detected():
    r = EntityResolver([_ent("e1", "Apex", ["Delta"]), _ent("e2", "Beta", ["Delta"])])
    amb = r.ambiguities()
    assert any(a["name"] == "delta" for a in amb)


def test_ambiguous_strict_raises():
    r = EntityResolver([_ent("e1", "Apex", ["Delta"]), _ent("e2", "Beta", ["Delta"])])
    with pytest.raises(AuroraError) as exc:
        r.resolve("Delta", strict=True)
    assert exc.value.error_code == "ENTITY_RESOLUTION_AMBIGUOUS"


def test_rename_via_alias_in_corpus(snapshot, name_to_entity):
    # Monolith Corp is imported with aliases; a later reference by old name resolves
    r = EntityResolver(snapshot.entities)
    assert r.resolve("Monolith Corporation") == name_to_entity["Monolith Corp"]

"""Provisional entity / observation staging helpers (engine 0.1.39+).

Staged unresolved mentions become entities with type PROVISIONAL and/or
``metadata.provisional=true``. Observations that used staging set
``metadata.subject_provisional`` / ``object_provisional``.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Union


def _meta(obj: Any) -> dict:
    if isinstance(obj, Mapping):
        m = obj.get("metadata") or {}
        return m if isinstance(m, dict) else {}
    m = getattr(obj, "metadata", None) or {}
    return m if isinstance(m, dict) else {}


def is_provisional_entity(entity: Any) -> bool:
    """True when entity is type PROVISIONAL or metadata.provisional is set."""
    if entity is None:
        return False
    if isinstance(entity, Mapping):
        et = entity.get("entity_type")
    else:
        et = getattr(entity, "entity_type", None)
    if et == "PROVISIONAL":
        return True
    return bool(_meta(entity).get("provisional"))


def observation_subject_provisional(obs: Any) -> bool:
    """True when the observation subject was staged as provisional at import."""
    if obs is None:
        return False
    return bool(_meta(obs).get("subject_provisional"))


def observation_object_provisional(obs: Any) -> bool:
    if obs is None:
        return False
    return bool(_meta(obs).get("object_provisional"))


def observation_has_provisional_mention(obs: Any) -> bool:
    """Subject or object was staged provisional."""
    return observation_subject_provisional(obs) or observation_object_provisional(obs)

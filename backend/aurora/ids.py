"""Deterministic identifiers and content hashing.

Every id in AURORA is a deterministic function of stable content so that the
same logical object always receives the same id across runs and machines. This
is a hard requirement for reproducibility (spec §22, §29): we must never rely on
autoincrement row ids or random UUIDs for anything that participates in results.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def content_hash(*parts: Any) -> str:
    """Stable hash over an ordered list of parts.

    Parts are JSON-encoded with sorted keys so dict ordering never changes the
    hash. Returns a 16-char hex digest (64 bits) which is collision-safe at our
    scale and keeps ids readable.
    """
    h = hashlib.sha256()
    for p in parts:
        h.update(b"\x1f")  # unit separator between parts
        if isinstance(p, (dict, list)):
            h.update(json.dumps(p, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))
        else:
            h.update(str(p).encode("utf-8"))
    return h.hexdigest()[:16]


def prefixed_id(prefix: str, *parts: Any) -> str:
    """Deterministic id like ``ent_1a2b3c...`` derived from content."""
    return f"{prefix}_{content_hash(*parts)}"


def normalize_text(text: str) -> str:
    """Whitespace/case normalization used for hashing text content."""
    return " ".join((text or "").lower().split())

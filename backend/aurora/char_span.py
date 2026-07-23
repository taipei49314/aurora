"""Deterministic char_span alignment: locate text_excerpt inside document text.

Used at import (engine 0.1.20+) when an observation has document_id + text_excerpt
but no explicit char_span. Keeps span-level provenance without manual offsets.
"""
from __future__ import annotations

import re
from typing import List, Optional

# Ignore very short excerpts — too many false positives
_MIN_EXCERPT_LEN = 4


def align_char_span(document_text: str, text_excerpt: str) -> Optional[List[int]]:
    """Return ``[start, end]`` character offsets of *text_excerpt* in *document_text*.

    Search order (deterministic, first hit wins):
      1. Exact substring
      2. Case-insensitive substring (span covers original casing length)
      3. Whitespace-flexible regex (collapsed runs of whitespace)

    Offsets are half-open ``[start, end)`` into the original document string.
    Returns ``None`` when no confident match is found.
    """
    doc = document_text if isinstance(document_text, str) else ""
    ex = (text_excerpt if isinstance(text_excerpt, str) else "").strip()
    if not doc or not ex or len(ex) < _MIN_EXCERPT_LEN:
        return None

    # 1. Exact
    idx = doc.find(ex)
    if idx >= 0:
        return [idx, idx + len(ex)]

    # 2. Case-insensitive (same length; use original excerpt length)
    lower_doc = doc.lower()
    lower_ex = ex.lower()
    idx = lower_doc.find(lower_ex)
    if idx >= 0:
        return [idx, idx + len(ex)]

    # 3. Whitespace-flexible: tokens joined by \\s+
    tokens = [t for t in re.split(r"\s+", ex) if t]
    if len(tokens) >= 1:
        pattern = r"\s+".join(re.escape(t) for t in tokens)
        try:
            m = re.search(pattern, doc, flags=re.IGNORECASE | re.DOTALL)
        except re.error:
            m = None
        if m is not None:
            return [m.start(), m.end()]

    return None


def auto_align_observation(
    document_text: str,
    text_excerpt: str,
    existing_span: Optional[list] = None,
) -> Optional[List[int]]:
    """Return existing span if valid, else align excerpt against document."""
    if existing_span is not None:
        if isinstance(existing_span, (list, tuple)) and len(existing_span) >= 2:
            try:
                a, b = int(existing_span[0]), int(existing_span[1])
                if 0 <= a <= b <= len(document_text or "") or a <= b:
                    return [a, b] if a <= b else [b, a]
            except (TypeError, ValueError):
                pass
        elif isinstance(existing_span, dict):
            try:
                a, b = int(existing_span["start"]), int(existing_span["end"])
                return [a, b] if a <= b else [b, a]
            except (KeyError, TypeError, ValueError):
                pass
    return align_char_span(document_text, text_excerpt)

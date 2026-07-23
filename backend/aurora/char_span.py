"""Deterministic char_span alignment: locate text_excerpt inside document text.

Used at import (engine 0.1.20+) when an observation has document_id + text_excerpt
but no explicit char_span. Keeps span-level provenance without manual offsets.

0.1.24+: progressive prefix match (word then char) for near-prefix excerpts
that differ only by a trailing clause or punctuation.
"""
from __future__ import annotations

import re
from typing import List, Optional

# Ignore very short excerpts — too many false positives
_MIN_EXCERPT_LEN = 4
# Progressive prefix must keep at least this many characters / words
_MIN_PREFIX_LEN = 12
_MIN_PREFIX_WORDS = 3


def align_char_span(document_text: str, text_excerpt: str) -> Optional[List[int]]:
    """Return ``[start, end]`` character offsets of *text_excerpt* in *document_text*.

    Search order (deterministic, first hit wins):
      1. Exact substring
      2. Case-insensitive substring (span covers original casing length)
      3. Whitespace-flexible regex (collapsed runs of whitespace)
      4. Progressive word-prefix (drop trailing words until match)
      5. Progressive character-prefix (rstrip punct; drop tail)

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

    # 4. Progressive word-prefix (drop trailing words)
    if len(tokens) >= _MIN_PREFIX_WORDS:
        for n in range(len(tokens) - 1, _MIN_PREFIX_WORDS - 1, -1):
            cand = " ".join(tokens[:n]).rstrip(".,;:!?\"'")
            if len(cand) < _MIN_PREFIX_LEN:
                continue
            idx = doc.find(cand)
            if idx >= 0:
                return [idx, idx + len(cand)]
            idx = lower_doc.find(cand.lower())
            if idx >= 0:
                # Map to original casing length of candidate
                return [idx, idx + len(cand)]

    # 5. Progressive character-prefix (handles trailing punctuation drift)
    for end in range(len(ex) - 1, _MIN_PREFIX_LEN - 1, -1):
        cand = ex[:end].rstrip(".,;:!?\"' \t")
        if len(cand) < _MIN_PREFIX_LEN:
            continue
        # Prefer word boundary when possible
        if end < len(ex) and ex[end - 1 : end].isalnum() and ex[end : end + 1].isalnum():
            continue
        idx = doc.find(cand)
        if idx >= 0:
            return [idx, idx + len(cand)]
        idx = lower_doc.find(cand.lower())
        if idx >= 0:
            return [idx, idx + len(cand)]

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

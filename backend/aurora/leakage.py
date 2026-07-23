"""Temporal cutoff + future-leakage prevention (spec §19, §20).

A cutoff run may only use data whose ``observed_at`` is on or before the cutoff
date. Observations with missing dates are *excluded* from cutoff runs (we cannot
prove they belong to the past) and counted separately. ``assert_no_leakage``
re-checks the included set and raises FUTURE_DATA_LEAKAGE if anything slips
through.
"""
from __future__ import annotations

from datetime import date

from .errors import AuroraError


def _parse(d: str | None) -> date | None:
    if not d:
        return None
    try:
        return date.fromisoformat(d[:10])
    except ValueError:
        return None


def parse_cutoff(cutoff: str | None) -> date | None:
    if cutoff is None:
        return None
    c = _parse(cutoff)
    if c is None:
        raise AuroraError("INVALID_CUTOFF_DATE", f"cannot parse cutoff {cutoff!r}", stage="leakage")
    return c


def apply_cutoff(observations, sources, cutoff: str | None) -> dict:
    """Return the observation/source subset available at cutoff plus a manifest."""
    c = parse_cutoff(cutoff)
    if c is None:
        return {
            "observations": list(observations),
            "sources": list(sources),
            "manifest": {
                "cutoff_date": None,
                "included_observation_count": len(observations),
                "excluded_future_observation_count": 0,
                "excluded_undated_observation_count": 0,
            },
        }
    included, excluded_future, excluded_undated = [], 0, 0
    for o in observations:
        d = _parse(o.observed_at)
        if d is None:
            excluded_undated += 1
            continue
        if d <= c:
            included.append(o)
        else:
            excluded_future += 1

    # also restrict sources to those published on/before cutoff (undated sources
    # kept only if referenced by an included observation)
    referenced = {o.source_id for o in included}
    inc_sources = []
    for s in sources:
        d = _parse(s.published_at)
        if d is not None and d <= c:
            inc_sources.append(s)
        elif d is None and s.source_id in referenced:
            inc_sources.append(s)
    return {
        "observations": included,
        "sources": inc_sources,
        "manifest": {
            "cutoff_date": c.isoformat(),
            "included_observation_count": len(included),
            "excluded_future_observation_count": excluded_future,
            "excluded_undated_observation_count": excluded_undated,
        },
    }


def assert_no_leakage(observations, cutoff: str | None, run_id: str | None = None):
    c = parse_cutoff(cutoff)
    if c is None:
        return
    for o in observations:
        d = _parse(o.observed_at)
        if d is None or d > c:
            raise AuroraError(
                "FUTURE_DATA_LEAKAGE",
                f"observation {o.observation_id} dated {o.observed_at} is after cutoff {c.isoformat()}",
                stage="leakage", run_id=run_id, entity_ids=[o.subject_entity],
                source_ids=[o.source_id], details={"observed_at": o.observed_at, "cutoff": c.isoformat()},
            )

"""Temporal cutoff + future-leakage prevention (spec §19, §20).

A cutoff run may only use data that was *available* at the cutoff date. That
takes two dates, not one:

* ``Observation.observed_at`` -- when the underlying event happened.
* ``Source.published_at`` -- when the document carrying it became public.

Both must be on or before the cutoff. Checking only ``observed_at`` lets a
retrospective document leak: an article published in 2023 about hiring that
happened in 2020 would enter a 2021 cutoff run, even though nobody could have
read it in 2021. That is not an exotic input -- ``docs/import-schema.md`` tells
importers to put the *event* date in ``observed_at``, so retrospective sources
are the normal case for real dumps. It went unnoticed because the Northstar
generator sets both fields from the same variable, so the corpus that exercises
the backtest cannot produce the divergence.

Anything whose date cannot be established is *excluded* rather than assumed to
be old -- an undated observation, an observation whose source is undated, and an
observation whose source is not in the snapshot at all. Each is counted
separately in the manifest. ``assert_no_leakage`` re-checks the included set
against both dates and raises FUTURE_DATA_LEAKAGE if anything slipped through.
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


def _source_date(sources, source_id: str) -> date | None:
    """Publication date of one source, or None if it is undated or absent."""
    for s in sources:
        if s.source_id == source_id:
            return _parse(s.published_at)
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
                "excluded_future_source_observation_count": 0,
                "excluded_undated_source_observation_count": 0,
            },
        }
    # A source is usable at the cutoff only if it is known to have been
    # published by then. Undated and unknown sources are not usable, because
    # "we do not know when this became public" is not evidence that it was.
    usable_sources = {}
    for s in sources:
        d = _parse(s.published_at)
        if d is not None and d <= c:
            usable_sources[s.source_id] = s

    included, excluded_future, excluded_undated = [], 0, 0
    excluded_future_source, excluded_undated_source = 0, 0
    for o in observations:
        d = _parse(o.observed_at)
        if d is None:
            excluded_undated += 1
            continue
        if d > c:
            excluded_future += 1
            continue
        if o.source_id not in usable_sources:
            sd = _source_date(sources, o.source_id)
            if sd is not None and sd > c:
                excluded_future_source += 1
            else:
                excluded_undated_source += 1
            continue
        included.append(o)

    # Every source known to be public by the cutoff stays available, whether or
    # not an included observation happens to cite it -- same as before. What
    # changed is only that undated sources no longer ride in on a reference.
    inc_sources = list(usable_sources.values())
    return {
        "observations": included,
        "sources": inc_sources,
        "manifest": {
            "cutoff_date": c.isoformat(),
            "included_observation_count": len(included),
            "excluded_future_observation_count": excluded_future,
            "excluded_undated_observation_count": excluded_undated,
            # Observations dated before the cutoff whose document was not yet
            # public then, or whose document cannot be dated at all.
            "excluded_future_source_observation_count": excluded_future_source,
            "excluded_undated_source_observation_count": excluded_undated_source,
        },
    }


def assert_no_leakage(observations, sources, cutoff: str | None,
                      run_id: str | None = None):
    """Re-check an included set against both dates.

    ``sources`` is required, not optional. A check that can be called without
    the half of the data it is supposed to inspect reports success on the half
    it can see, which is how the source-date leak survived in the first place.
    """
    c = parse_cutoff(cutoff)
    if c is None:
        return
    published = {s.source_id: _parse(s.published_at) for s in sources}
    for o in observations:
        d = _parse(o.observed_at)
        if d is None or d > c:
            raise AuroraError(
                "FUTURE_DATA_LEAKAGE",
                f"observation {o.observation_id} dated {o.observed_at} is after cutoff {c.isoformat()}",
                stage="leakage", run_id=run_id, entity_ids=[o.subject_entity],
                source_ids=[o.source_id], details={"observed_at": o.observed_at, "cutoff": c.isoformat()},
            )
        sd = published.get(o.source_id)
        if sd is None or sd > c:
            raise AuroraError(
                "FUTURE_DATA_LEAKAGE",
                f"observation {o.observation_id} comes from source {o.source_id}, "
                f"published {sd.isoformat() if sd else 'unknown'}, which was not "
                f"public at cutoff {c.isoformat()}",
                stage="leakage", run_id=run_id, entity_ids=[o.subject_entity],
                source_ids=[o.source_id],
                details={"observed_at": o.observed_at,
                         "source_published_at": sd.isoformat() if sd else None,
                         "cutoff": c.isoformat()},
            )

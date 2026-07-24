# Release cadence (mode B)

## Goals

Fewer, more meaningful releases. Avoid 0.1.x noise from navigation-only tweaks.

## Bump rules

| Change type | Bump `ENGINE_VERSION`? |
|-------------|------------------------|
| Docs, loop log, typos | **No** |
| Single deep-link / one filter chip | **No** (batch or unversioned) |
| Import/adapters/schema/lint behavior | **Yes** (patch or minor) |
| Scoring/clustering/classify change | **Yes** |
| API contract change | **Yes** if clients depend on it |
| Persistence that affects run hash / storage | **Yes** |

## Process

1. Ship work on `master` with honest commits.
2. When a pack is ready: one coordinated version touch (`config.py`, `__init__.py`, `pyproject.toml`, README badge, `CHANGELOG.md`).
3. Gate: `python scripts/check_engine.py` (full suite when SQLAlchemy available).
4. Tag optional later; engine string is the source of truth for local demos.

## Major versions (0.2 / 1.0)

Reserve for milestones (e.g. real-dump pathway proven, Windows full API tests, documented release checklist green). Not for loop micro-tasks.

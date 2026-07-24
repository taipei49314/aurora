# Autonomous progress loop log

Cadence: every ~30 minutes (plan → execute → test → git push).

## 2026-07-24 cycle-1

- **Planned:** Unblock Windows CI/local gate without MSVC (greenlet/SQLAlchemy install fails); align package version with ENGINE_VERSION.
- **Shipped:** `requirements-engine-test.txt`, `scripts/check_engine.py`, `--engine-only` on `check_all.py`, Makefile targets, version **0.1.32**, README install path.
- **Tests:** `python scripts/check_engine.py` — ALL OK (demo, version-sync, pytest-engine ignoring API/persistence, validate-example, adapters doctor).
- **Next suggestion:** Hypothesis table → Explorer deep-link (provenance UX continuity).

## 2026-07-24 cycle-2

- **Planned:** Dashboard hypothesis table row → Hypothesis Explorer deep-link (GOOD_FIRST_ISSUES suggested next).
- **Shipped (v0.1.32, combined with engine-only gate):**
  - Dashboard name column links to `/hypotheses?id=<hypothesis_id>`
  - Hypothesis Explorer reads `id` / `hypothesis_id` / `h`, highlights open card, scroll-into-view, URL stays shareable on expand/collapse
  - Docs: CHANGELOG, GOOD_FIRST_ISSUES #30, evolution-loop
- **Tests:** `python scripts/check_engine.py` — ALL OK (engine 0.1.32; pytest engine suite green).
- **Commit:** `2b72540` (code + docs already on master; this note documents cycle-2 UX slice inside that ship).
- **Next suggestion:** Status count chips → Hypothesis Explorer `?status=` filter; or `subject_raw` staging; human: PatentsView real dump / Actions PAT.

## 2026-07-24 cycle-3

- **Planned:** Dashboard status count chips → Hypothesis Explorer `?status=` filter (GOOD_FIRST_ISSUES / evolution-loop next).
- **Shipped (v0.1.33):**
  - Dashboard status cards link to `/hypotheses?status=<STATUS>`
  - Hypothesis Explorer All / per-status chips; URL `?status=` / `?s=`; composes with `?id=`
  - Docs: CHANGELOG, GOOD_FIRST_ISSUES #31, evolution-loop, README badge
- **Tests:** `python scripts/check_engine.py` — ALL OK (engine 0.1.33).
- **Commit:** `94cf45c`
- **Next suggestion:** Table Status badge dual deep-link; or `subject_raw` staging; human: PatentsView dump / Actions PAT.

## 2026-07-24 cycle-4

- **Planned:** Dashboard table Status badge dual deep-link (`?status=` + `?id=`).
- **Shipped (v0.1.34):** Status badge and name open `/hypotheses?status=&id=`; docs GOOD_FIRST_ISSUES #32, evolution-loop, CHANGELOG, badge.
- **Tests:** `python scripts/check_engine.py` — ALL OK (engine 0.1.34).
- **Commit:** `25fbb5f`
- **Next suggestion:** DiscoveryMap/Timeline shareable `?id=`; or `subject_raw` staging; human: PatentsView dump / Actions PAT.

## 2026-07-24 cycle-5

- **Planned:** DiscoveryMap / Timeline hypothesis picker → shareable `?id=` URL.
- **Shipped (v0.1.35):** Both pages read/write `?id=` (aliases); invalid id warning + fallback; docs #33.
- **Tests:** `python scripts/check_engine.py` — ALL OK (engine 0.1.35).
- **Commit:** `2c90757`
- **Next suggestion:** Explorer → Map/Timeline cross-links with same `?id=`; or `subject_raw`; human: PatentsView / Actions PAT.

## 2026-07-24 cycle-6

- **Planned:** Explorer → Discovery Map / Timeline cross-links with same `?id=`.
- **Shipped (v0.1.36):** Explorer detail links to Map/Timeline/Bottleneck Lab; Map↔Timeline↔Explorer reciprocal links; docs #34.
- **Tests:** `python scripts/check_engine.py` — ALL OK (engine 0.1.36).
- **Commit:** `41acea1`
- **Next suggestion:** Bottleneck Lab cluster → Explorer `?id=`; or `subject_raw`; human: PatentsView / Actions PAT.

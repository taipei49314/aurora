# Autonomous progress loop log

## Policy (mode B — since 2026-07-24)

- Cadence: about **every 2 hours** (not 30 minutes).
- **No micro version spam.** Do not bump `ENGINE_VERSION` for one deep-link, docs-only, or loop-log-only work.
- Version bump only for a **coherent pack**: engine/import/adapters/schema/tests or multi-file non-trivial feature, with tests.
- Tiny leftovers: either batch into one pack, or commit **without** version bump.
- Flow still: plan → execute → test → git push (no force-push).

## Legacy note

Cycles 1–7 on 2026-07-24 used 30-minute micro releases (0.1.32–0.1.37). That cadence is **retired**.

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

## 2026-07-24 cycle-7

- **Planned:** Bottleneck Lab cluster name → Explorer `?id=` deep-link.
- **Shipped (v0.1.37):** Cluster → Explorer `?status=&id=`; map/timeline secondary; entity_id → Data Explorer; docs #35.
- **Tests:** `python scripts/check_engine.py` — ALL OK (engine 0.1.37).
- **Commit:** `0853314`
- **Next suggestion:** self-audit Windows engine-only note; or `subject_raw`; human: PatentsView / Actions PAT.

## 2026-07-24 cycle-8 (mode B)

- **Mode B:** coherent pack; version bump **yes** (data contract + import behavior + tests, not UX-only).
- **Planned:** First-class `subject_raw` / `object_raw` mention staging (GOOD_FIRST_ISSUES / evolution-loop).
- **Shipped (v0.1.38):**
  - `Observation.subject_raw` / `object_raw`; import derive + metadata fallback; subject_raw-only resolve
  - Unresolved errors carry raw_value + subject_raw in message
  - API stats (`observations_with_subject_raw`, `observations_subject_raw_differs`); export round-trip
  - Data Explorer column + detail; JSON Schema + import-schema gap closed
  - self-audit: Windows engine-only gate documented under known limitations
- **Tests:** `python scripts/check_engine.py` — ALL OK (engine 0.1.38; includes `tests/test_subject_raw.py`).
- **Commit:** `0f05a58`
- **Next suggestion:** provisional entities for unresolved mentions (explicit type policy); human: PatentsView real dump / Actions PAT.

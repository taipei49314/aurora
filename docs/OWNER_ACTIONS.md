# OWNER_ACTIONS — aurora v0.1.47 release candidate

Branch: `closure/aurora-20260807`  
Cursor must **not** merge, force-push, delete tags, or publish the GitHub Release.

## Context

- Latest **public** GitHub Release: `v0.1.31` (2026-07-24)
- Declared engine on this branch: **0.1.47** (`ENGINE_VERSION` / `pyproject` / README / CHANGELOG)
- Drift from `v0.1.31` → HEAD is **real unreleased work** (not accidental bumps), plus post-`0.1.46` commits that changed run hashing and added Atlas submit without a version bump — corrected to **0.1.47** on this branch.

## Required owner actions

1. **Review** branch `closure/aurora-20260807` (open a PR to `master` if desired).
2. **Merge** only after CI is green on the PR (`check-all` + engine version sanity).
3. After merge, create annotated tag **`v0.1.47`** on the merged default-branch SHA.
4. **Publish** GitHub Release `v0.1.47` using `CHANGELOG.md` section `[0.1.47]` (and roll-up notes from `0.1.32`–`0.1.46` if you want a single public catch-up release).
5. Do **not** rewrite or delete historical tags `v0.1.1`–`v0.1.31`.

## Explicit non-actions for Cursor

- No merge of own PR
- No force-push
- No tag delete/rewrite
- No GitHub Release publish from this agent

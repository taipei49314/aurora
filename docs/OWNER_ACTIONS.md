# OWNER_ACTIONS — aurora v0.1.49 release candidate

Branch: `master` (local commits ahead of `origin/master`)

Automation must **not** force-push, delete tags, or publish the GitHub Release.

## Context

- The local repository contains tag `v0.1.47`; verify the current public release
  state before publishing anything.
- Declared engine on this branch: **0.1.49** (`ENGINE_VERSION` / `pyproject` /
  README / CHANGELOG). `FEATURE_VERSION` remains `0.1.47` because feature
  construction did not change.
- The `0.1.49` pack adds a real USPTO PatentsView integration corpus,
  digest-bound lineage, current API field fidelity, and source retrieval-time
  preservation on top of the `0.1.48` model-semantic fixes.

## Required owner actions

1. **Review** the local commits and diff against `origin/master`.
2. **Push** only after the full local gate is green; let GitHub Actions run
   `check-all` plus the engine-version sanity check.
3. After CI is green on the intended release SHA, create annotated tag
   **`v0.1.49`**.
4. **Publish** GitHub Release `v0.1.49` using `CHANGELOG.md` section `[0.1.49]`.
5. Do **not** rewrite or delete historical tags.

## Explicit non-actions for automation

- No merge of own PR
- No force-push
- No tag delete/rewrite
- No GitHub Release publish from this agent

# Release checklist (open source)

Use this for each public tag.

## Pre-flight

- [ ] `make check-all` (or `python scripts/check_all.py`) green
- [ ] `make demo` (or CLI demo) produces classifications
- [ ] No secrets in tree (search for tokens/keys)
- [ ] `CHANGELOG.md` updated for the version
- [ ] `ENGINE_VERSION` / package `__version__` match tag intent
- [ ] README “What this is / is not” still accurate

## GitHub

- [ ] Repository **public** (if intentional)
- [ ] Description + topics set (see below)
- [ ] LICENSE visible on repo home
- [ ] Default branch pushed with release commit
- [ ] Annotated tag `v0.1.1` (or current)
- [ ] GitHub Release notes pasted from CHANGELOG section

### Suggested topics

`research` `reproducible-research` `local-first` `discovery` `epistemic`
`no-llm` `industry-analysis` `python` `deterministic`

### Suggested description

> Local-first engine that finds unnamed industries from evidence — deterministic, no LLM at runtime, no stock tips.

## After release

- [ ] Pin repo on profile (optional)
- [ ] One short post linking README + honesty section
- [ ] Open 1–2 “good first issue” labels if seeking contributors

## Do not claim in release notes

- Real-world early discovery of a named industry without a public retro dump
- Investment performance
- Production multi-tenant SaaS readiness

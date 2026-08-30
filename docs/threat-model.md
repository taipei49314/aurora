# Threat Model

## Scope and security objective

AURORA is a local-first, single-user research engine, not a multi-tenant service.
Its primary protection goals are the integrity and traceability of imported
evidence, deterministic research outputs, cutoff honesty, and isolation of test
ground truth from runtime decisions. This document describes controls present in
the repository; it is not a claim that the application is hardened for an
untrusted network or hostile local users.

The authoritative implementation surfaces are the import pipeline under
`backend/aurora/`, the FastAPI layer in `backend/api.py`, the local persistence
stores, and the optional Atlas and md-brain adapters. Vulnerability-reporting
instructions and the supported-version policy remain in `SECURITY.md`.

## Assets and inputs

Assets in scope are:

- imported entities, sources, observations and optional documents, including
  their dates, licenses, raw text, paths and provenance identifiers;
- the taxonomy and versioned engine/scoring configuration;
- insert-once persisted `Snapshot` and `ResearchRun` records, manifest hashes, hypotheses,
  evidence ids and score explanations;
- the local SQLite database and any JSON or fleet-report files the operator asks
  AURORA to write; and
- optional findings sent to a user-selected Frontier Atlas URL or an md-brain
  Vault.

Import packages are allowed to be malformed, incomplete or factually wrong.
They cross an input-validation boundary; they are not treated as authenticated
evidence. The local operator, filesystem, taxonomy file and executable used for
an explicitly requested md-brain ingest are trusted under the current model.

## Trust boundaries

### 1. Import package to normalized snapshot

`import_package` validates required fields and controlled vocabularies, resolves
entity references, reports structured row errors, creates generated
content-derived ids while preserving caller-supplied stable ids, and calculates
exact, declared, event-level and near-duplicate source groups.
Ambiguous entity names are reported rather than silently selected. The default
staged type, `PROVISIONAL`, is not a cluster member, but callers may assign a
different staged entity type; clustering filters by type rather than the
`metadata.provisional` flag.

These controls protect structure and accounting. They do not authenticate a
publisher, verify that excerpts are true, validate every opaque metadata field,
or discover a missing source. Declared independence, event ids, reliability
tiers, dates and licenses still depend on adapter and corpus quality.

### 2. Snapshot to research run

The core engine is standard-library Python and performs no external API or LLM
call during import, clustering, scoring or classification. Input text is data for
tokenization and feature construction, not an instruction channel to a model.
Pipeline stages are deterministic functions of the normalized snapshot,
taxonomy and configuration, with sorted tie-breaking and recorded versions.

Historical runs require both `Observation.observed_at` and the cited
`Source.published_at` to be on or before the cutoff. Undated, missing-source and
future-publication observations are excluded, and a second hard check raises if
one survives. The same supplied taxonomy is used unless the caller selects a
different file; the engine records a taxonomy version but does not prove the
taxonomy itself was historically available.

### 3. Runtime evaluation data

Northstar labels live under `tests/ground_truth/`. Engine modules do not import
that path, and a test scans `backend/aurora/*.py` for direct `ground_truth` or
`labels.json` references. Ground-truth metrics are test-time evaluation, not an
input to runtime classification.

This guard is repository-specific and literal. It is not a general information-
flow proof against every possible mislabeled or evaluation-derived field in an
import package.

### 4. API and browser boundary

The FastAPI application has no authentication or authorization layer and its
CORS middleware allows every origin, method and header. It accepts JSON package
uploads, replaces the process's current snapshot, creates runs and backtests,
returns imported documents and observations, and can persist the current
snapshot to `backend/aurora.db`.

`docker-compose.yml` binds both services to `0.0.0.0` inside their containers and
publishes ports 8000 and 5173. Therefore the API and frontend must be exposed
only on interfaces and networks trusted by the operator. AURORA does not provide
a tenant boundary, login, rate limit, upload-size limit or encrypted transport.
The Compose stack is a local development/research deployment, not a secure
internet-facing configuration.

### 5. Persistence and integrity identifiers

Snapshot ids are derived from stable row ids. The versioned input manifest hash
serializes the complete normalized entity, source, observation and document
records in stable order; a `ResearchRun` also records a compact result manifest
hash and the configuration/version metadata used to produce it. JSON is the
portable audit format, and SQLite round trips are tested to preserve run results.

These hashes detect changes when trusted software recomputes and compares them.
They are not digital signatures, do not establish who supplied the data, and do
not prevent a process with filesystem access from replacing both an artifact and
its recorded hash. Files and SQLite data are not encrypted by AURORA.

### 6. Optional external companions

Network submission to Frontier Atlas occurs only when the CLI receives
`--atlas`; without it, the core run makes no Atlas request. The submitted report
states observed run outputs. `atlas.push_run` registers predictions only when it
is passed a `null_model` dictionary marked usable; the intended producer is
`retention_null_model`, while the demo CLI currently passes no baseline and
therefore submits findings only. The adapter does not cryptographically prove
that an arbitrary caller-supplied dictionary came from a backtest. The vendored
Atlas client is digest-pinned against the intentionally copied upstream version.

md-brain ingest occurs only with `--brain`. AURORA writes a local fleet report,
resolves the explicit or `PATH`-selected `mdbrain` executable, and launches it
with the requested Vault. Both integrations catch their own adapter errors so a
failed handoff does not invalidate the already completed research run.

Opt-in does not make either destination trusted. A user-selected Atlas URL can
receive report content, and a user-selected executable runs with the current
user's permissions. Destination authentication, transport policy, Vault access
control and the behavior of those external systems are outside AURORA's core
guarantees.

## Threats, controls and residual risk

| Threat | Present control | Residual risk / boundary |
|---|---|---|
| Malformed rows or unknown enums | Layered import validation and structured row errors | Valid-looking false claims and opaque metadata are not fact-checked |
| Syndicated sources inflate evidence | Exact hash, declared group, shared event id and MinHash-LSH near-duplicate grouping; scoring uses resolved independent groups | Bad or missing adapter metadata and paraphrased reprints can overstate independence |
| Entity alias poisoning or ambiguity | External-id/name resolution, explicit ambiguity errors, provisional metadata and optional hard lints | Wrong but unique identifiers or aliases remain trusted input; a caller-assigned clusterable provisional type can enter clustering, and all staged rows can affect TF-IDF document frequency |
| Future information leaks into a cutoff | Event-date and source-publication filtering plus a hard re-check | Historically inappropriate taxonomy content and incorrect source dates are not automatically detected |
| Hype or keywords force a conclusion | No fixed industry-keyword bonus, separate hype and counterevidence penalties, transparent gates | Adversarial or low-quality text can still change TF-IDF features and graph inputs |
| Unsupported relationships appear as facts | Value-chain edges require relational observations and carry evidence ids; hypothesis outputs retain observation ids | Source truth and completeness are not verified; some derived bottleneck notes are fixed heuristics |
| Run inputs or outputs change unnoticed | Content-addressed ids, versioned full-input manifest hash, compact result hash, deterministic replay tests | Hashes are unsigned and depend on trusted code and storage |
| Ground truth contaminates runtime | Test-only label path and source scan for direct references | Literal scan is not a complete taint-analysis system |
| Unauthorized API use or data disclosure | Intended local, single-user deployment | No auth, permissive CORS, published Compose ports, and endpoints that expose imported text |
| Resource exhaustion | None beyond normal parser and process behavior | Uploads and in-memory runs/backtests have no application-level quotas |
| Sensitive or unlicensed text is redistributed | First-class license fields and optional public-corpus/document/span lint policies | Lints are opt-in; exports and API responses do not redact content or enforce license terms |
| Optional companion exfiltrates or mutates data | Explicit CLI flags and adapter error isolation | Chosen URL, executable and Vault remain operator-trusted external boundaries |

## Outputs and provenance expectations

For an auditable run, retain the import package or normalized snapshot together
with the `ResearchRun`. The run identifies its snapshot, cutoff, engine, feature
and taxonomy versions, algorithm and scoring configuration, input/result hashes,
leakage counts, stage timings and hypotheses. Each hypothesis retains its entity
and observation ids, score explanation, supporting/counterevidence ids, missing
evidence and disconfirmation conditions.

Those fields support replay and review; they do not turn an observation into an
authenticated fact. Public claims should preserve the distinction between
"AURORA classified this cluster at this cutoff" and "this industry exists."

## Explicit non-goals and limits

- Multi-user authentication, authorization, tenant isolation and safe public
  hosting.
- Protection from a malicious local administrator or process that can read or
  replace repository, database, report or taxonomy files.
- Cryptographic source authenticity, signed artifacts, encryption at rest or
  secret management.
- Automated factual verification, malware scanning of uploaded files, legal
  clearance, redaction or privacy classification.
- Live crawling, runtime LLM classification, broker integration or trading
  advice.
- A claim that deterministic output is necessarily correct; determinism makes a
  result replayable, not true.

## Verification

- `tests/test_import_dedup.py` covers schema errors, idempotent re-import,
  independent-source collapse and the versioned full-input manifest hash.
- `tests/test_entity_resolution.py` covers aliases and ambiguity;
  `tests/test_external_id_resolution.py` covers external-id resolution and
  disambiguation.
- `tests/test_leakage_backtest.py` covers event/source cutoff enforcement and
  hard leakage failures.
- `tests/test_errors_isolation.py::test_engine_source_never_reads_ground_truth`
  enforces the current runtime/test-data boundary.
- `tests/test_scoring_determinism_divergence.py` and `tests/test_persistence.py`
  cover repeatability and persistence round trips.
- `tests/test_api.py` exercises upload, export and persistence behavior with an
  in-process `TestClient`; it does not establish network hardening.
- `tests/test_vendored_sdk_pinned.py`, `tests/test_atlas_module.py` and
  `tests/test_brain_module.py` cover the optional companion contracts without
  contacting a real external service in the tests.
- `python scripts/check_engine.py` is the offline engine gate. Security-sensitive
  defects should be reported through the private process in `SECURITY.md`.

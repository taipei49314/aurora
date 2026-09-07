"""Real offline package input and run artifact output.

The Northstar demo generates its corpus in memory (``datasets/northstar``).
Real research needs the other two ends of the pipeline made explicit:

* ``load_package`` reads a real offline package (a ``package.json`` file or a
  directory holding one) into the same ``{entities, sources, observations}``
  dict ``import_package`` already validates, so demo and real data share one
  schema, one validation path, and one evidence model.
* ``write_run_artifacts`` persists everything a later reader needs to audit the
  run without re-running it: the exact run report submitted to Atlas, a
  manifest that separates deterministic content hashes from non-deterministic
  timestamps, and per-finding evidence traces (cluster -> hypothesis ->
  observation -> source -> excerpt).

Nothing here invents content: the report is the exact text submitted, and the
traces point at stored observation/source rows.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

_GIT_REVISION: str | None = None


def load_package(path: str | Path) -> tuple[dict, dict]:
    """Load a real offline package. Returns ``(package, meta)``.

    ``path`` may be a package file (any name) or a directory containing
    ``package.json``. The file is the same shape the Northstar generator emits:
    ``{entities: [...], sources: [...], observations: [...]}`` with optional
    ``license`` and ``meta`` blocks. Validation happens in ``import_package``;
    this function only reads bytes and metadata.
    """
    path = Path(path)
    if path.is_dir():
        path = path / "package.json"
    if not path.is_file():
        raise FileNotFoundError(f"package not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    for key in ("entities", "sources", "observations"):
        if not isinstance(raw.get(key), list):
            raise ValueError(f"package {path} is missing the '{key}' list")
    meta = dict(raw.get("meta") or {})
    meta.setdefault("dataset_id", path.stem)
    meta.setdefault("dataset_version", "unversioned")
    meta["package_path"] = str(path.resolve())
    meta["package_sha256"] = __import__("hashlib").sha256(
        path.read_bytes()).hexdigest()
    meta["license"] = (raw.get("license") or "").strip()
    return raw, meta


def git_revision(repo_dir: str | Path | None = None) -> str:
    """The real git revision of the running code, or '' when unavailable.

    The mothership contract (frontier-atlas MOTHERSHIP.md) treats
    ``code_revision`` as what makes a run reproducible and allows the empty
    string when a module cannot know its own revision. Cached so one process
    reports one revision even across many runs.
    """
    global _GIT_REVISION
    if _GIT_REVISION is not None:
        return _GIT_REVISION
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir, capture_output=True, text=True, timeout=10,
            check=True,
        )
        revision = result.stdout.strip()
        _GIT_REVISION = revision if len(revision) == 40 else ""
    except (OSError, subprocess.SubprocessError):
        _GIT_REVISION = ""
    return _GIT_REVISION


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def build_run_manifest(run, snapshot, package_meta: dict, *,
                       taxonomy_path: str, report_text: str) -> dict:
    """Deterministic run identity first; wall-clock metadata kept separate.

    The report *text* embeds the run's own creation timestamp (the mothership
    contract builds dedup on it), so the whole-file ``report_sha256`` is
    non-deterministic across replays and is reported as such. The findings
    content itself is deterministic; ``findings_sha256`` covers only the
    FINDING lines.
    """
    import hashlib

    findings_hash = hashlib.sha256()
    for line in report_text.splitlines():
        if line.startswith("FINDING "):
            findings_hash.update(line.encode("utf-8"))
    counts = getattr(snapshot, "counts", {}) or {}
    deterministic = {
        "snapshot_id": snapshot.snapshot_id,
        "run_id": run.run_id,
        "cutoff_date": run.cutoff_date,
        "engine_version": run.engine_version,
        "feature_version": run.feature_version,
        "taxonomy_version": run.taxonomy_version,
        "input_manifest_hash": run.input_manifest_hash,
        "result_manifest_hash": run.result_manifest_hash,
        "findings_sha256": findings_hash.hexdigest(),
        "taxonomy_path": taxonomy_path,
        "package": {
            "dataset_id": package_meta.get("dataset_id"),
            "dataset_version": package_meta.get("dataset_version"),
            "package_sha256": package_meta.get("package_sha256"),
            "license": package_meta.get("license"),
            "provenance": package_meta.get("provenance"),
        },
        "counts": {k: counts.get(k) for k in sorted(counts)},
        "hypothesis_count": len(run.hypotheses),
    }
    nondeterministic = {
        # Same input replays to the same hashes but a new wall-clock stamp;
        # recorded here so differences are visible instead of hidden.
        "run_created_at": run.created_at,
        "snapshot_created_at": snapshot.created_at,
        "manifest_written_at": _utcnow(),
        # Includes the run's creation timestamp, so it differs per replay:
        "report_sha256": hashlib.sha256(report_text.encode("utf-8")).hexdigest(),
    }
    return {
        "deterministic": deterministic,
        "nondeterministic": nondeterministic,
        "code_revision": git_revision(),
        "note": ("Same input package, config, taxonomy, cutoff, and code "
                 "revision reproduce every 'deterministic' value. The "
                 "'nondeterministic' timestamps are recorded, never reused "
                 "as identity."),
    }


def build_finding_traces(run, snapshot) -> list[dict]:
    """One trace per finding-bearing hypothesis, with its full evidence chain.

    Chain: hypothesis (status/score/band) -> entity ids -> observation ids ->
    observation rows (verbatim excerpt, span) -> source rows (title, url,
    hash). ``evidence_kind`` labels what each observation is: the raw fact is
    the source's excerpt; the engine's classification is separate.
    """
    sources = {s.source_id: s for s in getattr(snapshot, "sources", []) or []}
    observations = {o.observation_id: o
                    for o in getattr(snapshot, "observations", []) or []}
    traces = []
    for h in run.hypotheses:
        obs_rows = []
        for obs_id in (h.observation_ids or [])[:50]:
            o = observations.get(obs_id)
            if o is None:
                continue
            source = sources.get(o.source_id)
            obs_rows.append({
                "observation_id": o.observation_id,
                "observation_type": o.observation_type,
                # Raw fact as recorded (verbatim from the source record):
                "evidence_kind": "source_recorded_fact",
                "text_excerpt": o.text_excerpt,
                "observed_at": o.observed_at,
                "char_span": o.char_span,
                "source": None if source is None else {
                    "source_id": source.source_id,
                    "title": source.title,
                    "publisher": source.publisher,
                    "url_or_local_path": source.url_or_local_path,
                    "content_hash": source.content_hash,
                    "reliability_tier": source.reliability_tier,
                },
                # Heuristic field carried by the package row itself, not a
                # statistical probability:
                "package_confidence": o.confidence,
            })
        traces.append({
            "hypothesis_id": h.hypothesis_id,
            "generated_name": h.generated_name,
            "status": h.status,
            "overall_score": h.overall_score,
            # Heuristic band from the weighted score (>=70 HIGH, >=50 MEDIUM,
            # >=30 LOW else VERY_LOW) — not a confidence interval:
            "heuristic_confidence_band": h.confidence_band,
            "entity_ids": h.entity_ids,
            "missing_evidence": list(h.missing_evidence or []),
            "engine_summary": h.summary,
            "observations": obs_rows,
        })
    return traces


def write_run_artifacts(out_dir: str | Path, run, snapshot, package_meta: dict,
                        *, taxonomy_path: str, report_text: str,
                        atlas_result: dict | None = None) -> dict:
    """Write run.md / run_manifest.json / findings.jsonl under ``out_dir``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "run.md").write_text(report_text, encoding="utf-8")
    manifest = build_run_manifest(run, snapshot, package_meta,
                                  taxonomy_path=taxonomy_path,
                                  report_text=report_text)
    if atlas_result is not None:
        manifest["atlas_submission"] = atlas_result
    (out / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    lines = []
    for trace in build_finding_traces(run, snapshot):
        lines.append(json.dumps(trace, ensure_ascii=False, sort_keys=True))
    (out / "findings.jsonl").write_text(
        "".join(line + "\n" for line in lines), encoding="utf-8")
    return {"directory": str(out.resolve()), "report": str(out / "run.md"),
            "manifest": str(out / "run_manifest.json"),
            "findings": str(out / "findings.jsonl")}

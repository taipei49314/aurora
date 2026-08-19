"""Send a research run's contract-shaped report into an md-brain Vault.

AURORA stays stdlib-only: it does not import md-brain. It writes the same
FINDING report Atlas would receive, then calls ``mdbrain ingest``. That opens
an episodic proposal — experience, not an Atlas claim. Failure must not fail
the research run.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from . import atlas

__all__ = ["BrainError", "fleet_report_path", "ingest_run", "write_fleet_report"]

MODULE_ID = "aurora"


class BrainError(RuntimeError):
    """md-brain call was refused, or a local precondition failed."""


def fleet_report_path(run, directory: str | Path) -> Path:
    run_id = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in str(run.run_id))
    return Path(directory) / f"{run_id}.fleet.md"


def resolve_mdbrain(explicit: str | None = None) -> str:
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_file():
            return str(path)
        raise BrainError(f"mdbrain binary not found: {explicit}")
    found = shutil.which("mdbrain")
    if not found:
        raise BrainError("mdbrain is not on PATH; pass --brain-bin or install md-brain")
    return found


def write_fleet_report(
    run,
    snapshot=None,
    *,
    directory: str | Path,
    inputs: str = "",
) -> Path:
    """Write the Atlas-shaped FINDING report for mdbrain ingest to extract."""
    report = atlas.build_report(run, snapshot, inputs=inputs)
    if len(report) == 0:
        raise BrainError("this run has no citable findings; not sending an empty report")
    path = fleet_report_path(run, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.render(), encoding="utf-8", newline="\n")
    return path


def ingest_run(
    run,
    snapshot=None,
    *,
    vault: str | Path,
    mdbrain_bin: str | None = None,
    report_dir: str | Path | None = None,
    inputs: str = "",
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """Write the fleet report and call mdbrain ingest. Returns a proposal summary."""
    vault_path = Path(vault).expanduser().resolve()
    if not vault_path.is_dir():
        raise BrainError(f"Vault is not a directory: {vault_path}")
    directory = Path(report_dir) if report_dir is not None else Path.cwd() / "reports"
    report_path = write_fleet_report(run, snapshot, directory=directory, inputs=inputs)
    binary = resolve_mdbrain(mdbrain_bin)
    completed = runner(
        [
            binary,
            "--vault",
            str(vault_path),
            "ingest",
            str(report_path),
            "--module",
            MODULE_ID,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise BrainError(detail or f"mdbrain ingest exit {completed.returncode}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise BrainError("mdbrain ingest did not return a JSON proposal") from exc
    if not isinstance(payload, dict) or "id" not in payload:
        raise BrainError("mdbrain ingest proposal is missing id")
    return {
        "proposal_id": payload["id"],
        "status": payload.get("status"),
        "target_path": payload.get("target_path"),
        "report_path": str(report_path),
    }

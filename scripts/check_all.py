#!/usr/bin/env python3
"""Local pre-push gate: unit/integration tests + key demos/cases.

Does not require network. Exit non-zero on first failure.

  PYTHONPATH=backend python scripts/check_all.py
  PYTHONPATH=backend python scripts/check_all.py --quick   # pytest only
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(label: str, cmd: list[str]) -> None:
    print("=" * 72)
    print(f"CHECK: {label}")
    print(" ", " ".join(cmd))
    print("-" * 72)
    env = {**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": "backend"}
    # Prefer explicit PYTHONPATH for child
    import os

    child_env = os.environ.copy()
    child_env["PYTHONPATH"] = str(ROOT / "backend")
    # adapters import needs repo root
    child_env["PYTHONPATH"] = str(ROOT / "backend") + os.pathsep + str(ROOT)
    r = subprocess.run(cmd, cwd=str(ROOT), env=child_env)
    if r.returncode != 0:
        print(f"FAIL: {label} (exit {r.returncode})", file=sys.stderr)
        raise SystemExit(r.returncode)
    print(f"OK: {label}\n")


def require_same_artifact(label: str, committed: Path, generated: Path) -> None:
    """Fail when a committed generated artifact is stale or was hand-edited."""
    print("=" * 72)
    print(f"CHECK: {label}")
    try:
        committed_bytes = committed.read_bytes()
        generated_bytes = generated.read_bytes()
    except OSError as exc:
        print(f"FAIL: {label}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    if committed_bytes != generated_bytes:
        committed_sha = hashlib.sha256(committed_bytes).hexdigest()
        generated_sha = hashlib.sha256(generated_bytes).hexdigest()
        print(
            f"FAIL: {label}: committed artifact differs from deterministic rebuild\n"
            f"  committed={committed} sha256:{committed_sha}\n"
            f"  generated={generated} sha256:{generated_sha}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    print(f"OK: {label}\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true", help="pytest only")
    ap.add_argument(
        "--engine-only",
        action="store_true",
        help="delegate to scripts/check_engine.py (no SQLAlchemy/greenlet)",
    )
    ap.add_argument(
        "--python",
        default=sys.executable,
        help="Python interpreter (default: current)",
    )
    args = ap.parse_args(argv)
    py = args.python

    if args.engine_only:
        # Avoid importing SQLAlchemy-backed tests on machines without MSVC/greenlet.
        r = subprocess.run([py, str(ROOT / "scripts" / "check_engine.py")], cwd=str(ROOT))
        return int(r.returncode)

    # basetemp under repo avoids Windows pytest-of-* temp cleanup PermissionError
    basetemp = ROOT / ".tmp" / "pytest"
    basetemp.mkdir(parents=True, exist_ok=True)
    run(
        "pytest",
        [
            py,
            "-m",
            "pytest",
            "tests/",
            "-q",
            "--tb=line",
            f"--basetemp={basetemp}",
        ],
    )
    if args.quick:
        print("ALL OK (quick)")
        return 0

    npm = shutil.which("npm")
    if not npm:
        print("FAIL: frontend-build: npm was not found", file=sys.stderr)
        return 1
    run("frontend-build", [npm, "run", "build", "--prefix", "frontend"])

    run(
        "validate-example",
        [py, "scripts/validate_package.py", "examples/real_mini_package.json", "--strict"],
    )
    run(
        "lint-example",
        [
            py,
            "scripts/lint_package.py",
            "examples/real_mini_package.json",
            "--strict",
            "--require-documents",
            "--no-provisional",
        ],
    )
    run(
        "lint-multisource",
        [
            py,
            "scripts/lint_package.py",
            "cases/multisource-iron-air/package.json",
            "--strict",
            "--require-documents",
            "--min-char-span-ratio",
            "0.5",
            "--no-provisional",
        ],
    )
    run(
        "lint-iron-air-mini",
        [
            py,
            "scripts/lint_package.py",
            "cases/iron-air-mini/package.json",
            "--strict",
            "--require-documents",
            "--min-char-span-ratio",
            "0.4",
            "--no-provisional",
        ],
    )
    run(
        "lint-iron-air-retro",
        [
            py,
            "scripts/lint_package.py",
            "cases/iron-air-retro/package.json",
            "--strict",
            "--require-documents",
            "--require-char-spans",
            "--no-provisional",
        ],
    )
    run("retro-case", [py, "scripts/run_retro_case.py", "cases/iron-air-retro"])
    run(
        "retro-scorecard",
        [py, "scripts/check_case_scorecard.py", "cases/iron-air-retro"],
    )
    run("multisource-case", [py, "scripts/build_multisource_case.py"])
    run(
        "multisource-scorecard",
        [py, "scripts/check_case_scorecard.py", "cases/multisource-iron-air"],
    )
    run(
        "iron-air-mini-scorecard",
        [py, "scripts/check_case_scorecard.py", "cases/iron-air-mini"],
    )
    generated_patentsview = ROOT / ".tmp" / "patentsview-package.generated.json"
    run(
        "patentsview-generate",
        [
            py,
            "-m",
            "adapters",
            "patentsview",
            "cases/patentsview-sample/dump.json",
            "-o",
            str(generated_patentsview.relative_to(ROOT)),
            "--strip",
            "--validate",
            "--strict",
        ],
    )
    require_same_artifact(
        "patentsview-generated-artifact",
        ROOT / "cases" / "patentsview-sample" / "package.json",
        generated_patentsview,
    )
    run(
        "patentsview-scorecard",
        [py, "scripts/check_case_scorecard.py", "cases/patentsview-sample"],
    )
    run(
        "lint-patentsview",
        [
            py,
            "scripts/lint_package.py",
            "cases/patentsview-sample/package.json",
            "--strict",
            "--require-documents",
            "--min-char-span-ratio",
            "1.0",
            "--no-provisional",
            "--public-corpus",
        ],
    )
    run(
        "resolve-smoke",
        [
            py,
            "scripts/resolve_entities.py",
            "cases/multisource-iron-air/package.json",
            "--ref",
            "ext:lei:LEI-FERRO-DEMO",
        ],
    )
    run("adapters-doctor", [py, "-m", "adapters", "doctor"])
    run(
        "openalex-case",
        [
            py,
            "-m",
            "adapters",
            "openalex",
            "adapters/fixtures/openalex_sample.json",
            "-o",
            "cases/openalex-sample/package.json",
            "--strip",
            "--validate",
            "--strict",
        ],
    )
    run(
        "openalex-scorecard",
        [py, "scripts/check_case_scorecard.py", "cases/openalex-sample"],
    )
    run(
        "lint-openalex",
        [
            py,
            "scripts/lint_package.py",
            "cases/openalex-sample/package.json",
            "--strict",
            "--require-documents",
            "--require-char-spans",
            "--no-provisional",
        ],
    )
    print("=" * 72)
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

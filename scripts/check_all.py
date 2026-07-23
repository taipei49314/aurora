#!/usr/bin/env python3
"""Local pre-push gate: unit/integration tests + key demos/cases.

Does not require network. Exit non-zero on first failure.

  PYTHONPATH=backend python scripts/check_all.py
  PYTHONPATH=backend python scripts/check_all.py --quick   # pytest only
"""
from __future__ import annotations

import argparse
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true", help="pytest only")
    ap.add_argument(
        "--python",
        default=sys.executable,
        help="Python interpreter (default: current)",
    )
    args = ap.parse_args(argv)
    py = args.python

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

    run(
        "validate-example",
        [py, "scripts/validate_package.py", "examples/real_mini_package.json", "--strict"],
    )
    run(
        "lint-example",
        [py, "scripts/lint_package.py", "examples/real_mini_package.json", "--strict"],
    )
    run(
        "lint-multisource",
        [
            py,
            "scripts/lint_package.py",
            "cases/multisource-iron-air/package.json",
            "--strict",
            "--require-documents",
        ],
    )
    run("retro-case", [py, "scripts/run_retro_case.py", "cases/iron-air-retro"])
    run("multisource-case", [py, "scripts/build_multisource_case.py"])
    run(
        "multisource-scorecard",
        [py, "scripts/check_case_scorecard.py", "cases/multisource-iron-air"],
    )
    run(
        "patentsview-scorecard",
        [
            py,
            "-m",
            "adapters",
            "patentsview",
            "cases/patentsview-sample/dump.json",
            "-o",
            "cases/patentsview-sample/package.json",
            "--strip",
            "--validate",
            "--strict",
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
    print("=" * 72)
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

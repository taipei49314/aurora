#!/usr/bin/env python3
"""Windows-friendly engine gate: no SQLAlchemy/greenlet required.

Runs demo smoke + pytest excluding API/persistence modules that need C++
wheels for greenlet on some Windows Python installs.

  PYTHONPATH=backend python scripts/check_engine.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    py = sys.executable
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "backend") + os.pathsep + str(ROOT)
    basetemp = ROOT / ".tmp" / "pytest-engine"
    basetemp.mkdir(parents=True, exist_ok=True)

    steps = [
        (
            "demo-cli",
            [py, str(ROOT / "backend" / "aurora" / "cli.py")],
        ),
        (
            "version-sync",
            [
                py,
                "-c",
                (
                    "from aurora import __version__; from aurora.config import ENGINE_VERSION; "
                    "assert __version__ == ENGINE_VERSION, (__version__, ENGINE_VERSION); "
                    "print('engine', ENGINE_VERSION)"
                ),
            ],
        ),
        (
            "pytest-engine",
            [
                py,
                "-m",
                "pytest",
                "tests/",
                "-q",
                "--tb=line",
                f"--basetemp={basetemp}",
                "--ignore=tests/test_api.py",
                "--ignore=tests/test_persistence.py",
            ],
        ),
        (
            "validate-example",
            [py, "scripts/validate_package.py", "examples/real_mini_package.json", "--strict"],
        ),
        (
            "adapters-doctor",
            [py, "-m", "adapters", "doctor"],
        ),
    ]
    for label, cmd in steps:
        print("=" * 72)
        print(f"ENGINE CHECK: {label}")
        print(" ", " ".join(cmd))
        print("-" * 72)
        r = subprocess.run(cmd, cwd=str(ROOT), env=env)
        if r.returncode != 0:
            print(f"FAIL: {label}", file=sys.stderr)
            return r.returncode
        print(f"OK: {label}\n")
    print("=" * 72)
    print("ENGINE CHECK ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

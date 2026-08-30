"""Build/install smoke proving packaged SQLite migrations work off-checkout."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

import pytest


pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]
HEAD_REVISION = "a7c5d9e1f203"
MIGRATION_RESOURCES = {
    "aurora/alembic.ini",
    "aurora/migrations/README",
    "aurora/migrations/env.py",
    "aurora/migrations/script.py.mako",
    "aurora/migrations/versions/ec328ff867b1_initial_schema_snapshots_entities_.py",
    "aurora/migrations/versions/a7c5d9e1f203_add_documents_table.py",
}


def _offline_subprocess_env():
    """Keep subprocesses functional without forwarding credentials or imports."""
    allowed = {
        "APPDATA",
        "COMSPEC",
        "HOME",
        "LANG",
        "LC_ALL",
        "LOCALAPPDATA",
        "PATH",
        "PATHEXT",
        "PROGRAMDATA",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "USERPROFILE",
        "WINDIR",
    }
    env = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in allowed
    }
    env["PIP_NO_INDEX"] = "1"
    return env


def _run(command, *, cwd, env=None):
    completed = subprocess.run(
        [str(part) for part in command],
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, (
        f"command failed: {' '.join(str(part) for part in command)}\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    return completed


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _expose_parent_test_dependencies_if_needed(python: Path) -> None:
    """Keep nested-venv runs offline when system-site omits the parent venv."""
    offline_env = _offline_subprocess_env()
    probe = subprocess.run(
        [str(python), "-I", "-c", "import alembic, sqlalchemy"],
        env=offline_env,
        text=True,
        capture_output=True,
    )
    if probe.returncode == 0:
        return

    # A venv created from inside another venv inherits the base interpreter's
    # system site, not the parent's site-packages. Link only the already-
    # installed test dependency roots; the Aurora wheel remains installed in
    # and imported from the clean child venv.
    import alembic
    import sqlalchemy

    dependency_roots = sorted(
        {
            str(Path(alembic.__file__).resolve().parents[1]),
            str(Path(sqlalchemy.__file__).resolve().parents[1]),
        }
    )
    child_site = _run(
        [
            python,
            "-I",
            "-c",
            "import sysconfig; print(sysconfig.get_paths()['purelib'])",
        ],
        cwd=python.parent,
        env=offline_env,
    ).stdout.strip()
    Path(child_site, "aurora_test_dependencies.pth").write_text(
        "\n".join(dependency_roots) + "\n", encoding="utf-8"
    )
    _run(
        [python, "-I", "-c", "import alembic, sqlalchemy"],
        cwd=python.parent,
        env=offline_env,
    )


def test_wheel_installs_with_migrations_and_runs_persistent_store_off_checkout(
    tmp_path,
):
    wheel_dir = tmp_path / "wheel"
    wheel_dir.mkdir()
    offline_env = _offline_subprocess_env()
    _run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            wheel_dir,
        ],
        cwd=ROOT,
        env=offline_env,
    )
    wheels = list(wheel_dir.glob("*.whl"))
    assert len(wheels) == 1
    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        wheel_contents = set(archive.namelist())
    assert MIGRATION_RESOURCES <= wheel_contents

    outside_dir = Path(tempfile.mkdtemp(prefix="aurora-wheel-smoke-"))
    try:
        assert ROOT != outside_dir and ROOT not in outside_dir.parents
        venv_dir = outside_dir / "venv"
        _run(
            [
                sys.executable,
                "-m",
                "venv",
                "--system-site-packages",
                venv_dir,
            ],
            cwd=outside_dir,
            env=offline_env,
        )
        python = _venv_python(venv_dir)
        _expose_parent_test_dependencies_if_needed(python)
        _run(
            [
                python,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-index",
                "--no-deps",
                wheel,
            ],
            cwd=outside_dir,
            env=offline_env,
        )

        smoke = """
import json
from pathlib import Path

import aurora
from sqlalchemy import inspect, text
from aurora.store_sql import Base, make_engine

repo = Path({repo!r}).resolve()
module = Path(aurora.__file__).resolve()
assert repo != module and repo not in module.parents
package = module.parent
assert (package / "alembic.ini").is_file()
assert (package / "migrations" / "env.py").is_file()
database = Path.cwd() / "installed.db"
engine = make_engine("sqlite:///" + database.as_posix())
tables = set(inspect(engine).get_table_names())
assert set(Base.metadata.tables) <= tables
assert "alembic_version" in tables
with engine.connect() as connection:
    revision = connection.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar_one()
print(json.dumps({{
    "module": str(module),
    "revision": revision,
    "tables": sorted(tables),
}}))
""".format(repo=str(ROOT))
        result = _run(
            [python, "-I", "-c", smoke], cwd=outside_dir, env=offline_env
        )
        report = json.loads(result.stdout.strip().splitlines()[-1])
        assert report["revision"] == HEAD_REVISION
        assert "documents" in report["tables"]
        assert Path(report["module"]).is_relative_to(venv_dir)
    finally:
        shutil.rmtree(outside_dir, ignore_errors=True)

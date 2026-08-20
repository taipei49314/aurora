"""Offline readiness checks for the Docker deployment contract."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.docker_audit import audit_stack, main


ROOT = Path(__file__).resolve().parents[1]


def _copy_stack_contract(tmp_path: Path) -> None:
    for relative in (
        "backend/Dockerfile",
        "frontend/Dockerfile",
        "frontend/vite.config.ts",
        "docker-compose.yml",
    ):
        source = ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


@pytest.mark.unit
def test_bundled_docker_stack_passes_static_audit():
    report = audit_stack(ROOT)
    assert report.ok, [issue.render() for issue in report.issues]
    assert report.checks >= 25


@pytest.mark.unit
def test_static_audit_catches_context_and_port_drift(tmp_path):
    _copy_stack_contract(tmp_path)
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    compose = compose.replace("build: ./backend", "build: ./wrong-backend")
    compose = compose.replace('      - "5173:5173"', '      - "5174:5173"')
    (tmp_path / "docker-compose.yml").write_text(compose, encoding="utf-8")

    report = audit_stack(tmp_path)
    messages = "\n".join(issue.message for issue in report.issues)
    assert not report.ok
    assert "backend build context must be ./backend" in messages
    assert "frontend must publish 5173:5173" in messages


@pytest.mark.unit
@pytest.mark.parametrize(
    ("relative", "old", "new", "expected"),
    (
        (
            "docker-compose.yml",
            "AURORA_API_PROXY_TARGET=http://backend:8000",
            "AURORA_API_PROXY_TARGET=http://localhost:8000",
            "frontend must set AURORA_API_PROXY_TARGET=http://backend:8000",
        ),
        (
            "frontend/vite.config.ts",
            '"http://localhost:8000"',
            '"http://backend:8000"',
            "API proxy target must default to http://localhost:8000",
        ),
    ),
)
def test_static_audit_catches_proxy_target_drift(tmp_path, relative, old, new, expected):
    _copy_stack_contract(tmp_path)
    path = tmp_path / relative
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")

    report = audit_stack(tmp_path)
    messages = "\n".join(issue.message for issue in report.issues)
    assert not report.ok
    assert expected in messages


@pytest.mark.unit
def test_cli_states_runtime_verification_is_still_required(capsys):
    assert main([str(ROOT)]) == 0
    output = capsys.readouterr().out
    assert "DOCKER STATIC AUDIT PASS" in output
    assert "Runtime start still requires verification on a Docker host." in output

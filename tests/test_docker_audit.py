"""Offline readiness checks for the Docker deployment contract."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.docker_audit import audit_stack, main


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.unit
def test_bundled_docker_stack_passes_static_audit():
    report = audit_stack(ROOT)
    assert report.ok, [issue.render() for issue in report.issues]
    assert report.checks >= 25


@pytest.mark.unit
def test_static_audit_catches_context_and_port_drift(tmp_path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "frontend").mkdir()
    source_files = (
        (ROOT / "backend" / "Dockerfile", tmp_path / "backend" / "Dockerfile"),
        (ROOT / "frontend" / "Dockerfile", tmp_path / "frontend" / "Dockerfile"),
    )
    for source, target in source_files:
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
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
def test_cli_states_runtime_verification_is_still_required(capsys):
    assert main([str(ROOT)]) == 0
    output = capsys.readouterr().out
    assert "DOCKER STATIC AUDIT PASS" in output
    assert "Runtime start still requires verification on a Docker host." in output

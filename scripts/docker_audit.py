#!/usr/bin/env python3
"""Audit AURORA's Docker contract without requiring Docker.

This is deliberately a static readiness check.  It verifies the small,
versioned contract between ``docker-compose.yml`` and the two Dockerfiles,
but it does not parse images, pull dependencies, or start containers.  A
passing report therefore never changes the self-audit's Docker status from
PARTIAL to PASS.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class AuditIssue:
    path: str
    message: str
    line: Optional[int] = None

    def render(self) -> str:
        location = self.path
        if self.line is not None:
            location = f"{location}:{self.line}"
        return f"{location}: {self.message}"


@dataclass(frozen=True)
class AuditReport:
    checks: int
    issues: Tuple[AuditIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


@dataclass
class _ComposeService:
    fields: Dict[str, str]
    lists: Dict[str, List[str]]


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _dockerfile_instructions(text: str) -> List[Tuple[str, str, int]]:
    """Return logical Dockerfile instructions as (name, args, line)."""
    logical: List[Tuple[str, str, int]] = []
    pending = ""
    pending_line = 0
    for number, raw_line in enumerate(text.splitlines(), 1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not pending:
            pending_line = number
        if stripped.endswith("\\"):
            pending += stripped[:-1].rstrip() + " "
            continue
        pending += stripped
        match = re.match(r"^([A-Za-z]+)\s+(.+)$", pending)
        if match:
            logical.append((match.group(1).upper(), match.group(2).strip(), pending_line))
        pending = ""
    if pending:
        match = re.match(r"^([A-Za-z]+)\s+(.+)$", pending)
        if match:
            logical.append((match.group(1).upper(), match.group(2).strip(), pending_line))
    return logical


def _read_text(path: Path, root: Path, issues: List[AuditIssue]) -> Optional[str]:
    relative = str(path.relative_to(root)).replace("\\", "/")
    if not path.is_file():
        issues.append(AuditIssue(relative, "required file is missing"))
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        issues.append(AuditIssue(relative, f"cannot read file: {exc}"))
        return None


def _audit_dockerfile(
    path: Path,
    root: Path,
    issues: List[AuditIssue],
    checks: List[int],
    expectations: Sequence[Tuple[str, Callable[[str], bool], str]],
) -> None:
    text = _read_text(path, root, issues)
    if text is None:
        return
    relative = str(path.relative_to(root)).replace("\\", "/")
    instructions = _dockerfile_instructions(text)
    for label, predicate, message in expectations:
        checks.append(1)
        match = next(
            ((name, args, line) for name, args, line in instructions if predicate(f"{name} {args}")),
            None,
        )
        if match is None:
            issues.append(AuditIssue(relative, f"missing {label}: {message}"))


def _parse_compose(path: Path, root: Path, issues: List[AuditIssue]) -> Dict[str, _ComposeService]:
    text = _read_text(path, root, issues)
    if text is None:
        return {}

    services: Dict[str, _ComposeService] = {}
    in_services = False
    current: Optional[_ComposeService] = None
    current_field: Optional[str] = None

    for number, raw_line in enumerate(text.splitlines(), 1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        content = raw_line.strip()
        match = re.match(r"^([A-Za-z0-9_.-]+):(?:\s*(.*))?$", content)

        if indent == 0:
            in_services = content == "services:"
            current = None
            current_field = None
            continue
        if not in_services:
            continue
        if indent == 2 and match:
            name = match.group(1)
            current = _ComposeService(fields={}, lists={})
            services[name] = current
            current_field = None
            continue
        if indent == 4 and match and current is not None:
            current_field = match.group(1)
            value = match.group(2)
            if value:
                current.fields[current_field] = _unquote(value)
            else:
                current.lists[current_field] = []
            continue
        if indent >= 6 and current is not None and current_field:
            if content.startswith("-"):
                current.lists.setdefault(current_field, []).append(_unquote(content[1:].strip()))
            else:
                issues.append(
                    AuditIssue(
                        str(path.relative_to(root)).replace("\\", "/"),
                        f"unsupported nested compose syntax near line {number}",
                        number,
                    )
                )
    return services


def _audit_compose(
    path: Path,
    root: Path,
    issues: List[AuditIssue],
    checks: List[int],
) -> None:
    services = _parse_compose(path, root, issues)
    relative = str(path.relative_to(root)).replace("\\", "/")

    def check(condition: bool, message: str) -> None:
        checks.append(1)
        if not condition:
            issues.append(AuditIssue(relative, message))

    check(set(services) == {"backend", "frontend"}, "services must be exactly backend and frontend")
    backend = services.get("backend")
    frontend = services.get("frontend")
    if backend is None or frontend is None:
        return

    check(backend.fields.get("build") == "./backend", "backend build context must be ./backend")
    check(frontend.fields.get("build") == "./frontend", "frontend build context must be ./frontend")
    check(
        "uvicorn api:app" in backend.fields.get("command", "")
        and "--host 0.0.0.0" in backend.fields.get("command", "")
        and "--port 8000" in backend.fields.get("command", ""),
        "backend command must expose uvicorn on 0.0.0.0:8000",
    )
    check(
        "npm run dev" in frontend.fields.get("command", "")
        and "--host 0.0.0.0" in frontend.fields.get("command", ""),
        "frontend command must run Vite on 0.0.0.0",
    )
    check("8000:8000" in backend.lists.get("ports", []), "backend must publish 8000:8000")
    check("5173:5173" in frontend.lists.get("ports", []), "frontend must publish 5173:5173")
    check(
        {"./backend:/app", "./datasets:/datasets", "./tests:/tests"}.issubset(
            set(backend.lists.get("volumes", []))
        ),
        "backend volumes must include backend, datasets, and tests",
    )
    check(
        {"./frontend:/app", "/app/node_modules"}.issubset(set(frontend.lists.get("volumes", []))),
        "frontend volumes must include source and anonymous node_modules",
    )
    check(
        "AURORA_TAXONOMY=/datasets/taxonomy/taxonomy.json"
        in backend.lists.get("environment", []),
        "backend must point AURORA_TAXONOMY at /datasets/taxonomy/taxonomy.json",
    )
    check("backend" in frontend.lists.get("depends_on", []), "frontend must depend on backend")


def audit_stack(root: Path) -> AuditReport:
    """Run the offline Docker contract audit rooted at *root*."""
    root = Path(root)
    issues: List[AuditIssue] = []
    checks: List[int] = []

    _audit_dockerfile(
        root / "backend" / "Dockerfile",
        root,
        issues,
        checks,
        (
            ("python base image", lambda line: line.startswith("FROM python:") and "-slim" in line, "use a slim Python image"),
            ("backend workdir", lambda line: line == "WORKDIR /app", "WORKDIR must be /app"),
            ("backend requirements copy", lambda line: line == "COPY requirements.txt .", "copy requirements.txt before install"),
            ("backend dependency install", lambda line: line.startswith("RUN pip install") and "-r requirements.txt" in line, "install backend requirements"),
            ("backend source copy", lambda line: line == "COPY . /app", "copy backend source into /app"),
            ("backend Python path", lambda line: line in {"ENV PYTHONPATH=/app", "ENV PYTHONPATH /app"}, "set PYTHONPATH=/app"),
            ("backend port", lambda line: line == "EXPOSE 8000", "expose port 8000"),
            ("backend command", lambda line: line.startswith("CMD ") and "uvicorn" in line and "api:app" in line and "8000" in line, "start the API on port 8000"),
        ),
    )
    _audit_dockerfile(
        root / "frontend" / "Dockerfile",
        root,
        issues,
        checks,
        (
            ("Node base image", lambda line: line.startswith("FROM node:"), "use a Node image"),
            ("frontend workdir", lambda line: line == "WORKDIR /app", "WORKDIR must be /app"),
            ("frontend package copy", lambda line: line == "COPY package.json ./", "copy package.json before install"),
            ("frontend dependency install", lambda line: line.startswith("RUN npm install"), "install frontend dependencies"),
            ("frontend source copy", lambda line: line == "COPY . /app", "copy frontend source into /app"),
            ("frontend port", lambda line: line == "EXPOSE 5173", "expose port 5173"),
            ("frontend command", lambda line: line.startswith("CMD ") and "npm" in line and "run" in line and "dev" in line, "start the Vite dev server"),
        ),
    )
    _audit_compose(root / "docker-compose.yml", root, issues, checks)
    return AuditReport(checks=len(checks), issues=tuple(issues))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    report = audit_stack(args.root)
    print(f"DOCKER STATIC AUDIT: {report.checks} checks")
    for issue in report.issues:
        print(f"FAIL: {issue.render()}")
    if not report.ok:
        print("DOCKER STATIC AUDIT FAILED")
        return 1
    print("DOCKER STATIC AUDIT PASS")
    print("Runtime start still requires verification on a Docker host.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

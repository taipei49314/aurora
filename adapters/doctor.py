"""Adapter doctor: list adapters, fixtures, and optional convert smoke."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).resolve().parent / "fixtures"


def _smoke_uspto() -> Tuple[bool, str]:
    from .uspto import convert_uspto

    raw = json.loads((FIX / "uspto_sample.json").read_text(encoding="utf-8"))
    pkg = convert_uspto(raw)
    n = len(pkg.get("sources") or [])
    return n > 0, f"sources={n}"


def _smoke_patentsview() -> Tuple[bool, str]:
    from .patentsview import convert_patentsview

    raw = json.loads((FIX / "patentsview_sample.json").read_text(encoding="utf-8"))
    pkg = convert_patentsview(raw)
    n = len(pkg.get("sources") or [])
    return n > 0, f"sources={n}"


def _smoke_jobs() -> Tuple[bool, str]:
    from .jobs import convert_jobs

    raw = json.loads((FIX / "jobs_sample.json").read_text(encoding="utf-8"))
    pkg = convert_jobs(raw)
    n = len(pkg.get("sources") or [])
    return n > 0, f"sources={n}"


def _smoke_news() -> Tuple[bool, str]:
    from .news import convert_news

    raw = json.loads((FIX / "news_sample.json").read_text(encoding="utf-8"))
    pkg = convert_news(raw)
    n = len(pkg.get("sources") or [])
    return n > 0, f"sources={n}"


ADAPTERS: List[Tuple[str, str, Callable[[], Tuple[bool, str]]]] = [
    ("uspto", "adapters/fixtures/uspto_sample.json", _smoke_uspto),
    ("patentsview", "adapters/fixtures/patentsview_sample.json", _smoke_patentsview),
    ("jobs", "adapters/fixtures/jobs_sample.json", _smoke_jobs),
    ("news", "adapters/fixtures/news_sample.json", _smoke_news),
    ("merge", "(compose packages)", lambda: (True, "no standalone fixture")),
]


def run_doctor(*, smoke: bool = True) -> int:
    print(f"AURORA adapters doctor  root={ROOT}")
    print(f"fixtures dir: {FIX}")
    failed = 0
    for name, fixture, fn in ADAPTERS:
        path = ROOT / fixture if not fixture.startswith("(") else None
        exists = path.is_file() if path else True
        status = "ok" if exists else "MISSING"
        print(f"  [{status:7}] {name:12}  {fixture}")
        if smoke and name != "merge":
            try:
                ok, detail = fn()
                print(f"             smoke: {'OK' if ok else 'FAIL'} {detail}")
                if not ok:
                    failed += 1
            except Exception as exc:  # noqa: BLE001
                print(f"             smoke: FAIL {type(exc).__name__}: {exc}")
                failed += 1
        if path and not exists:
            failed += 1
    return 1 if failed else 0

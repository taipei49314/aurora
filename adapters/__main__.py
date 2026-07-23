"""CLI: python -m adapters <command> ...

Commands:
  uspto        Convert USPTO-shaped JSON to an AURORA import package.
  patentsview  Convert PatentsView-compatible patent export JSON.
  jobs         Convert job-board JSON to an import package.
  news         Convert news/wire JSON to an import package.
  merge        Merge two or more import packages.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .doctor import run_doctor
from .jobs import convert_jobs
from .news import convert_news
from .package_util import merge_packages, package_stats, strip_package
from .patentsview import convert_patentsview
from .uspto import convert_uspto

ROOT = Path(__file__).resolve().parents[1]


def _write_pkg(pkg: dict, output: Optional[str], strip: bool) -> None:
    out_pkg = strip_package(pkg) if strip else pkg
    text = json.dumps(out_pkg, ensure_ascii=False, indent=2) + "\n"
    if output:
        Path(output).write_text(text, encoding="utf-8")
        print(f"wrote {output}", file=sys.stderr)
    else:
        sys.stdout.write(text)


def _maybe_validate(pkg: dict, *, validate: bool, run: bool, strict: bool) -> int:
    if not (validate or run):
        return 0
    sys.path.insert(0, str(ROOT / "backend"))
    from aurora import import_package  # noqa: WPS433

    snap = import_package(strip_package(pkg))
    n_err = len(snap.import_errors or [])
    print(
        f"import snapshot={snap.snapshot_id} "
        f"entities={len(snap.entities)} sources={len(snap.sources)} "
        f"obs={len(snap.observations)} errors={n_err} "
        f"independent={snap.counts.get('independent_source_count')}/"
        f"{snap.counts.get('raw_source_count')}",
        file=sys.stderr,
    )
    if n_err and strict:
        for e in snap.import_errors[:15]:
            print(f"  err: {e}", file=sys.stderr)
        return 1
    if run:
        from aurora import DEFAULT_CONFIG, Taxonomy, run_pipeline  # noqa: WPS433

        tax = Taxonomy.load(ROOT / "datasets" / "taxonomy" / "taxonomy.json")
        result = run_pipeline(snap, tax, DEFAULT_CONFIG, cutoff_date=None)
        print(
            f"run={result.run_id} hypotheses={len(result.hypotheses)}",
            file=sys.stderr,
        )
        for h in sorted(result.hypotheses, key=lambda x: -x.overall_score)[:5]:
            print(
                f"  {h.status:28} {h.overall_score:5.1f}  {h.generated_name}",
                file=sys.stderr,
            )
    return 0


def _emit_convert(
    name: str,
    pkg: dict,
    *,
    count_key: str,
    count_val: int,
    output: Optional[str],
    strip: bool,
    validate: bool,
    run: bool,
    strict: bool,
) -> int:
    stats = package_stats(pkg)
    print(
        f"adapter={name} {count_key}={count_val} "
        f"entities={stats['entities']} sources={stats['sources']} "
        f"observations={stats['observations']} orphans={stats['orphan_observations']}",
        file=sys.stderr,
    )
    if stats["orphan_observations"]:
        print("error: orphan observations (source_ref missing)", file=sys.stderr)
        return 1
    _write_pkg(pkg, output, strip)
    return _maybe_validate(pkg, validate=validate, run=run, strict=strict)


def _add_io_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("-o", "--output", help="Write package JSON (default: stdout)")
    p.add_argument(
        "--strip",
        action="store_true",
        help="Omit _adapter diagnostic key (engine-only three arrays)",
    )
    p.add_argument("--validate", action="store_true", help="Run import_package")
    p.add_argument("--run", action="store_true", help="Validate and run discovery")
    p.add_argument(
        "--strict",
        action="store_true",
        help="Non-zero exit if import reports row errors",
    )


def _cmd_uspto(args: argparse.Namespace) -> int:
    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    pkg = convert_uspto(raw, publisher=args.publisher)
    return _emit_convert(
        "uspto",
        pkg,
        count_key="patents_in",
        count_val=pkg.get("_adapter", {}).get("patent_count", 0),
        output=args.output,
        strip=args.strip,
        validate=args.validate,
        run=args.run,
        strict=args.strict,
    )


def _cmd_patentsview(args: argparse.Namespace) -> int:
    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    pkg = convert_patentsview(raw)
    return _emit_convert(
        "patentsview",
        pkg,
        count_key="patents_in",
        count_val=pkg.get("_adapter", {}).get("patent_count", 0),
        output=args.output,
        strip=args.strip,
        validate=args.validate,
        run=args.run,
        strict=args.strict,
    )


def _cmd_jobs(args: argparse.Namespace) -> int:
    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    pkg = convert_jobs(raw)
    return _emit_convert(
        "jobs",
        pkg,
        count_key="postings_in",
        count_val=pkg.get("_adapter", {}).get("posting_count", 0),
        output=args.output,
        strip=args.strip,
        validate=args.validate,
        run=args.run,
        strict=args.strict,
    )


def _cmd_news(args: argparse.Namespace) -> int:
    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    pkg = convert_news(raw)
    return _emit_convert(
        "news",
        pkg,
        count_key="articles_in",
        count_val=pkg.get("_adapter", {}).get("article_count", 0),
        output=args.output,
        strip=args.strip,
        validate=args.validate,
        run=args.run,
        strict=args.strict,
    )


def _cmd_merge(args: argparse.Namespace) -> int:
    packages: List[dict] = []
    for path in args.inputs:
        packages.append(json.loads(Path(path).read_text(encoding="utf-8")))
    pkg = merge_packages(packages)
    pkg["_adapter"] = {
        "id": "merge",
        "version": "0.1.0",
        "inputs": [str(p) for p in args.inputs],
        "input_count": len(args.inputs),
    }
    stats = package_stats(pkg)
    print(
        f"adapter=merge inputs={len(args.inputs)} "
        f"entities={stats['entities']} sources={stats['sources']} "
        f"observations={stats['observations']} orphans={stats['orphan_observations']}",
        file=sys.stderr,
    )
    if stats["orphan_observations"]:
        print("error: orphan observations after merge", file=sys.stderr)
        return 1
    _write_pkg(pkg, args.output, args.strip)
    return _maybe_validate(
        pkg, validate=args.validate, run=args.run, strict=args.strict
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m adapters")
    sub = parser.add_subparsers(dest="command", required=True)

    p_uspto = sub.add_parser("uspto", help="Convert USPTO-shaped JSON")
    p_uspto.add_argument("input", help="Path to patents JSON")
    p_uspto.add_argument("--publisher", default="USPTO")
    _add_io_flags(p_uspto)
    p_uspto.set_defaults(func=_cmd_uspto)

    p_pv = sub.add_parser(
        "patentsview",
        help="Convert PatentsView-compatible patent export JSON",
    )
    p_pv.add_argument("input", help="Path to PatentsView-shaped JSON")
    _add_io_flags(p_pv)
    p_pv.set_defaults(func=_cmd_patentsview)

    p_jobs = sub.add_parser("jobs", help="Convert job-board JSON")
    p_jobs.add_argument("input", help="Path to postings JSON")
    _add_io_flags(p_jobs)
    p_jobs.set_defaults(func=_cmd_jobs)

    p_news = sub.add_parser("news", help="Convert news/wire JSON")
    p_news.add_argument("input", help="Path to articles JSON")
    _add_io_flags(p_news)
    p_news.set_defaults(func=_cmd_news)

    p_merge = sub.add_parser("merge", help="Merge import packages")
    p_merge.add_argument(
        "inputs",
        nargs="+",
        help="Two or more package JSON paths",
    )
    _add_io_flags(p_merge)
    p_merge.set_defaults(func=_cmd_merge)

    p_doc = sub.add_parser("doctor", help="List adapters/fixtures and smoke-convert")
    p_doc.add_argument(
        "--no-smoke",
        action="store_true",
        help="Only list fixtures, do not convert",
    )
    p_doc.set_defaults(func=lambda a: run_doctor(smoke=not a.no_smoke))

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv

from similar_code_search.core import run
from similar_code_search.models import SearchReport


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="similar-code-search",
        description=(
            "Search GitHub for repositories similar to a query. Intended for "
            "novelty checks before building a new tool or implementation."
        ),
    )
    p.add_argument("query", help="Description or keywords of your project.")
    p.add_argument("-l", "--language", default=None,
                   help="Restrict to a GitHub-recognized language (e.g. python).")
    p.add_argument("--min-stars", type=int, default=5,
                   help="Minimum stars per candidate (default 5).")
    p.add_argument("-n", "--per-search", type=int, default=30,
                   help="Results to pull per backend before merge+rank (default 30).")
    p.add_argument("--top", type=int, default=10,
                   help="Papers to return after ranking (default 10).")
    p.add_argument("--readme-for", type=int, default=10,
                   help="Fetch READMEs for this many top candidates to enrich BM25 (default 10).")
    p.add_argument("-f", "--format", choices=["markdown", "json"], default="markdown",
                   help="Output format (default markdown).")
    return p


def _fmt_markdown(report: SearchReport, top: int) -> str:
    lines: list[str] = []
    kept = report.repos[:top]
    lines.append(
        f"Found {len(report.repos)} candidate repos via {', '.join(report.used) or '(none)'}"
        + (f" (language={report.language})" if report.language else "")
        + f". Top {len(kept)}:"
    )
    lines.append("")
    for i, r in enumerate(kept, 1):
        sc = f"{r.score:.2f}" if r.score is not None else "—"
        comps = r.score_components or {}
        comp_s = "  ".join(f"{k}={v:.2f}" for k, v in comps.items()) if comps else ""
        lines.append(f" {i:>2}. [{sc}] {r.full_name} — ★ {r.stars:,}  (pushed {r.pushed_at or '?'})")
        if r.description:
            lines.append(f"     {r.description}")
        lines.append(f"     {r.html_url}")
        if comp_s:
            lines.append(f"     {comp_s}")
        if r.matched_files:
            lines.append(f"     matched files: " + ", ".join(r.matched_files[:3]))
    if report.errors:
        lines.append("")
        lines.append("Backend errors: "
                     + "; ".join(f"{e['backend']}: {e['error']}" for e in report.errors))
    return "\n".join(lines)


def _fmt_json(report: SearchReport, top: int) -> str:
    payload = {
        "query": report.query,
        "language": report.language,
        "backends_used": report.used,
        "total_candidates": len(report.repos),
        "repos": [r.to_dict() for r in report.repos[:top]],
        "errors": report.errors,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)

    if not os.environ.get("GITHUB_TOKEN"):
        sys.stderr.write(
            "warning: GITHUB_TOKEN is unset. Unauthenticated GitHub search is "
            "limited to 10 req/min and code-search is disabled. Set GITHUB_TOKEN "
            "in your environment or .env for better recall.\n"
        )

    try:
        report = run(
            args.query,
            language=args.language,
            min_stars=args.min_stars,
            per_search=args.per_search,
            fetch_readme_for=args.readme_for,
        )
    except Exception as e:
        sys.stderr.write(f"error: {e}\n")
        return 3

    if args.format == "json":
        print(_fmt_json(report, args.top))
    else:
        print(_fmt_markdown(report, args.top))

    if not report.repos and report.errors:
        return 3
    if report.errors:
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from paper_search.bibtex import extract_query_from_bibtex, to_bibtex_all
from paper_search.core import run_search
from paper_search.download import download_all
from paper_search.sources import ALL_SOURCES, DEFAULT_SOURCES, REGISTRY


def _parse_sources(s: str) -> list[str]:
    names = [x.strip() for x in s.split(",") if x.strip()]
    bad = [n for n in names if n not in REGISTRY]
    if bad:
        raise argparse.ArgumentTypeError(
            f"unknown source(s): {', '.join(bad)}. Choose from: {', '.join(ALL_SOURCES)}"
        )
    return names


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="paper-search",
        description="Search academic papers across multiple sources, rank with BM25, optionally download PDFs.",
    )
    p.add_argument("query", help="Query string (keywords or free-form).")
    p.add_argument(
        "-n", "--total", type=int, default=50,
        help="Candidates to pull from each source before ranking (default: 50).",
    )
    p.add_argument(
        "--top", type=int, default=20,
        help="Papers to return after ranking (default: 20).",
    )
    p.add_argument(
        "-s", "--sources", type=_parse_sources, default=DEFAULT_SOURCES,
        help=f"Comma list of sources (default: {','.join(DEFAULT_SOURCES)}). "
             f"Choices: {', '.join(ALL_SOURCES)}.",
    )
    p.add_argument("--from", dest="year_from", type=int, default=None,
                   help="Lower year bound (inclusive). Defaults to year_to - 5.")
    p.add_argument("--to", dest="year_to", type=int, default=None,
                   help="Upper year bound (inclusive). Defaults to current year.")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="If set, download PDFs into this directory.")
    p.add_argument("-f", "--format", dest="format",
                   choices=["markdown", "json", "bibtex"], default=None,
                   help="Output format (default: markdown).")
    p.add_argument("--json", dest="json_flag", action="store_true",
                   help="Alias for --format json.")
    p.add_argument("--bibtex", dest="bibtex_flag", action="store_true",
                   help="Alias for --format bibtex.")
    return p


def _resolve_format(args: argparse.Namespace) -> str:
    picks = []
    if args.format:
        picks.append(args.format)
    if args.json_flag:
        picks.append("json")
    if args.bibtex_flag:
        picks.append("bibtex")
    uniq = list(dict.fromkeys(picks))
    if len(uniq) > 1:
        raise SystemExit(2)
    return uniq[0] if uniq else "markdown"


def _resolve_years(year_from, year_to):
    if year_to is None:
        year_to = _dt.date.today().year
    if year_from is None:
        year_from = year_to - 5
    if year_from > year_to:
        raise SystemExit(2)
    return year_from, year_to


def _fmt_markdown(result, query: str, year_range: tuple[int, int]) -> str:
    lines = []
    lines.append(
        f"Found {result.total_candidates} candidates across "
        f"{len(result.sources_used)} sources. Top {len(result.papers)}:"
    )
    lines.append("")
    for i, p in enumerate(result.papers, 1):
        sc = f"[{p.score:.2f}]" if p.score is not None else "[—]"
        authors = ", ".join(p.authors[:3]) + (" et al." if len(p.authors) > 3 else "")
        year = p.year or "n.d."
        idline = p.arxiv_id and f"arXiv:{p.arxiv_id}" or (p.doi and f"doi:{p.doi}") or ""
        cites = f"cites {p.citation_count}" if p.citation_count else ""
        srcs = ", ".join(p.sources)
        extra = "  ·  ".join(x for x in [idline, cites, srcs] if x)
        lines.append(f" {i:>2}. {sc} {p.title} — {authors}, {year}")
        if extra:
            lines.append(f"     {extra}")
        if p.downloaded_to:
            lines.append(f"     ↓ {p.downloaded_to}")
    if result.errors:
        lines.append("")
        lines.append(
            "Errors: "
            + "; ".join(f"{e['source']}: {e['error']}" for e in result.errors)
        )
    return "\n".join(lines)


def _fmt_json(result, query: str, year_range: tuple[int, int]) -> str:
    from paper_search.bibtex import to_bibtex

    papers_out = []
    for p in result.papers:
        d = p.model_dump()
        d["bibtex"] = to_bibtex(p)
        papers_out.append(d)
    payload = {
        "query": query,
        "year_range": list(year_range),
        "sources_used": result.sources_used,
        "total_candidates": result.total_candidates,
        "papers": papers_out,
        "errors": result.errors,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def _async_main(args: argparse.Namespace) -> int:
    fmt = _resolve_format(args)  # may raise SystemExit(2)

    # Prevent the common mistake of passing a relative -o path when the CLI
    # was launched via `uv run --directory <skill>`: cwd is the skill folder,
    # and a relative path would silently land inside the skill repo.
    if args.output is not None and not args.output.is_absolute():
        cwd = Path.cwd()
        skill_root = Path(__file__).resolve().parents[2]
        try:
            cwd.relative_to(skill_root)
            in_skill = True
        except ValueError:
            in_skill = False
        if in_skill:
            sys.stderr.write(
                f"error: -o was given a relative path ({args.output!s}) while the CLI "
                f"is running inside the skill directory ({cwd}). Pass an absolute "
                f"path so PDFs don't land inside the skill repo.\n"
            )
            return 2

    year_from, year_to = _resolve_years(args.year_from, args.year_to)
    sources = [REGISTRY[n]() for n in args.sources]

    # If the user pasted a BibTeX entry as the query, extract the title.
    effective_query = extract_query_from_bibtex(args.query) or args.query

    result = await run_search(
        sources,
        effective_query,
        year_from=year_from,
        year_to=year_to,
        per_source=args.total,
        top=args.top,
    )

    if args.output:
        await download_all(result.papers, args.output)

    if fmt == "bibtex":
        print(to_bibtex_all(result.papers), end="")
    elif fmt == "json":
        print(_fmt_json(result, effective_query, (year_from, year_to)))
    else:
        print(_fmt_markdown(result, effective_query, (year_from, year_to)))

    if not result.papers and len(result.errors) == len(args.sources):
        return 3
    if result.errors and result.papers:
        return 4
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        return 130
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 2


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Literal

from dotenv import load_dotenv

from paper_summarize.ingest import load
from paper_summarize.summarize import ask, summarize


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="paper-summarize",
        description=(
            "Summarize an academic paper (arXiv ID / DOI / URL / local PDF) "
            "into structured fields via the Claude API. Supports follow-up "
            "Q&A on the same paper (cached paper body)."
        ),
    )
    p.add_argument("input", help="arXiv ID (e.g. 1706.03762), DOI, HTTPS URL, or local PDF path.")
    p.add_argument(
        "-m", "--model", choices=["sonnet", "opus"], default="sonnet",
        help="Claude model (default: sonnet = claude-sonnet-4-6; opus = claude-opus-4-7).",
    )
    p.add_argument(
        "-q", "--ask", dest="question", default=None,
        help="Instead of a structured summary, ask a free-form question about the paper.",
    )
    p.add_argument(
        "-f", "--format", choices=["markdown", "json"], default="markdown",
        help="Output format (default markdown).",
    )
    p.add_argument(
        "--max-tokens", type=int, default=None,
        help="Override response max_tokens (default 4000 for summary, 2000 for ask).",
    )
    return p


def _require_api_key() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.stderr.write(
            "error: ANTHROPIC_API_KEY is unset. Set it in your environment or a .env file.\n"
        )
        raise SystemExit(2)


def _fmt_markdown_summary(summary, usage: dict, paper_ref: str) -> str:
    lines = []
    title = summary.title or paper_ref
    lines.append(f"# {title}")
    if summary.authors:
        lines.append(f"_{', '.join(summary.authors)}_")
    lines.append("")
    lines.append(f"**TL;DR.** {summary.tldr}")
    lines.append("")
    lines.append("## Problem")
    lines.append(summary.problem)
    lines.append("")
    lines.append("## Approach")
    lines.append(summary.approach)
    lines.append("")
    lines.append("## Results")
    lines.append(summary.results)
    if summary.contributions:
        lines.append("")
        lines.append("## Contributions")
        for c in summary.contributions:
            lines.append(f"- {c}")
    if summary.limitations:
        lines.append("")
        lines.append("## Limitations")
        for l in summary.limitations:
            lines.append(f"- {l}")
    if summary.keywords:
        lines.append("")
        lines.append("**Keywords:** " + ", ".join(summary.keywords))
    lines.append("")
    lines.append(_fmt_usage(usage))
    return "\n".join(lines)


def _fmt_usage(u: dict) -> str:
    return (
        f"_Tokens: in={u['input_tokens']}  out={u['output_tokens']}  "
        f"cache_read={u['cache_read_input_tokens']}  "
        f"cache_write={u['cache_creation_input_tokens']}_"
    )


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    _require_api_key()

    try:
        paper = load(args.input)
    except Exception as e:
        sys.stderr.write(f"error: could not load input: {e}\n")
        return 2

    if not paper.text.strip():
        sys.stderr.write("error: extracted text was empty; is this a scanned PDF?\n")
        return 3

    paper_ref = paper.identifier

    if args.question:
        max_tokens = args.max_tokens or 2000
        answer, usage = ask(
            paper.text, args.question,
            model=args.model, paper_ref=paper_ref, max_tokens=max_tokens,
        )
        if args.format == "json":
            print(json.dumps({
                "paper_ref": paper_ref,
                "question": args.question,
                "answer": answer,
                "usage": usage,
            }, ensure_ascii=False, indent=2))
        else:
            print(f"**Q:** {args.question}\n")
            print(answer)
            print()
            print(_fmt_usage(usage))
        return 0

    max_tokens = args.max_tokens or 4000
    summary, usage = summarize(
        paper.text,
        model=args.model, paper_ref=paper_ref, max_tokens=max_tokens,
    )
    if args.format == "json":
        payload = summary.model_dump()
        payload["_paper_ref"] = paper_ref
        payload["_usage"] = usage
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_fmt_markdown_summary(summary, usage, paper_ref))
    return 0


if __name__ == "__main__":
    sys.exit(main())

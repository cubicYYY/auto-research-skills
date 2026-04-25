"""Live: summarize an arXiv paper, then ask a follow-up and verify cache reuse.

Requires network + ANTHROPIC_API_KEY. Uses Sonnet 4.6.
"""
from __future__ import annotations

import os
import sys

from paper_summarize.ingest import load
from paper_summarize.summarize import ask, summarize


ARXIV_ID = "1706.03762"  # Attention Is All You Need — small enough to be fast


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is unset — skipping live test.", file=sys.stderr)
        return 2

    print(f"Loading arXiv {ARXIV_ID}…")
    paper = load(ARXIV_ID)
    print(f"  text_len={len(paper.text):,}  title={paper.title!r}")

    print("\n1) Structured summary…")
    summary, u1 = summarize(paper.text, paper_ref=paper.identifier)
    print(f"   tldr: {summary.tldr}")
    print(f"   usage: in={u1['input_tokens']} out={u1['output_tokens']} "
          f"cache_write={u1['cache_creation_input_tokens']} "
          f"cache_read={u1['cache_read_input_tokens']}")

    print("\n2) Follow-up question (should hit cache)…")
    answer, u2 = ask(
        paper.text,
        "What exact dataset and batch size were used for the English→German task?",
        paper_ref=paper.identifier,
    )
    print(f"   answer: {answer[:300]}…" if len(answer) > 300 else f"   answer: {answer}")
    print(f"   usage: in={u2['input_tokens']} out={u2['output_tokens']} "
          f"cache_write={u2['cache_creation_input_tokens']} "
          f"cache_read={u2['cache_read_input_tokens']}")

    if u2["cache_read_input_tokens"] > 0:
        print("\n✓ follow-up hit the cache as expected.")
        return 0
    print("\n! cache_read_input_tokens was 0 on the follow-up — check prefix stability.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

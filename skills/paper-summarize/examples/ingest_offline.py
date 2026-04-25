"""Offline: exercise the ingestion dispatcher on a URL-shaped input and
validate the schema round-trips. No network (dispatch is tested without
actually fetching), no ANTHROPIC_API_KEY required.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from paper_summarize.ingest import (
    ARXIV_ABS_RE, ARXIV_BARE_RE, ARXIV_PDF_RE, DOI_RE,
)
from paper_summarize.models import PaperSummary


def _classify(s: str) -> str:
    """Mirror of ingest.load's dispatch, returns the kind without fetching."""
    p = Path(s).expanduser()
    if p.exists() and p.is_file():
        return "pdf-file"
    for rx in (ARXIV_ABS_RE, ARXIV_PDF_RE):
        if rx.search(s):
            return "arxiv"
    if ARXIV_BARE_RE.match(s):
        return "arxiv"
    if DOI_RE.match(s):
        return "doi"
    if s.startswith("http://") or s.startswith("https://"):
        return "url"
    return "unknown"


def main() -> int:
    cases = [
        ("1706.03762",                                      "arxiv"),
        ("arXiv:1706.03762v3",                              "arxiv"),
        ("https://arxiv.org/abs/2205.14135",                "arxiv"),
        ("https://arxiv.org/pdf/2205.14135v2",              "arxiv"),
        ("10.48550/arXiv.1706.03762",                       "doi"),
        ("https://doi.org/10.48550/arXiv.1706.03762",       "doi"),
        ("https://example.com/paper.pdf",                   "url"),
        ("not a real input",                                "unknown"),
    ]

    failed = 0
    for inp, expected in cases:
        got = _classify(inp)
        ok = "✓" if got == expected else "✗"
        print(f"  {ok} {inp!r:<55} → {got} (expected {expected})")
        if got != expected:
            failed += 1
    assert failed == 0, f"{failed} dispatch cases failed"

    # Schema round-trip
    s = PaperSummary(
        title="Test",
        authors=["A. Author"],
        tldr="One sentence.",
        problem="p",
        approach="a",
        results="r",
        contributions=["c1"],
        limitations=["l1"],
        keywords=["k1", "k2"],
    )
    as_json = s.model_dump_json()
    s2 = PaperSummary.model_validate_json(as_json)
    assert s2 == s

    print("\n✓ dispatch + schema round-trip OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

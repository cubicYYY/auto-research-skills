"""Two-pass keyword-boosted search.

Demonstrates the `paper-search` + `paper-summarize` loop described in
`SKILL.md` under "Two-pass keyword-boosted search":

  1. Run paper-search for the user's query.
  2. Summarize the top-K hits via paper-summarize (structured JSON).
  3. Union each summary's `keywords[]`, drop terms already in the query,
     cap at 4 new terms, and re-run paper-search with the enriched query.
  4. Report the delta — papers surfaced by pass 2 that pass 1 missed.

Invokes both CLIs via `uv run --directory` (the same path Claude takes),
so this script doubles as a smoke test for cross-skill composition.

Requires network + ANTHROPIC_API_KEY for pass 2 on (for summarization).
Without a key, the script runs pass 1 only and exits with a clear message.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve()
PAPER_SEARCH_DIR = HERE.parents[1]
BUNDLE_DIR = PAPER_SEARCH_DIR.parents[1]
PAPER_SUMMARIZE_DIR = BUNDLE_DIR / "skills" / "paper-summarize"

QUERY = "repository level code auditing with LLM agents"
TOP_K_TO_SUMMARIZE = 3     # how many pass-1 hits to feed into summarize
MAX_NEW_TERMS = 4          # cap on keywords added to pass-2 query


def _normalize_token(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _query_token_set(query: str) -> set[str]:
    return {_normalize_token(t) for t in re.findall(r"[A-Za-z0-9]+", query) if t}


def _kw_already_in_query(kw: str, query_tokens: set[str]) -> bool:
    """A keyword is 'already in the query' if every alphanumeric word of it
    appears in the query — tolerates phrase-vs-word mismatch without
    dropping a multi-word keyword just because one token overlaps."""
    parts = [_normalize_token(p) for p in re.findall(r"[A-Za-z0-9]+", kw) if p]
    if not parts:
        return True
    return all(p in query_tokens for p in parts)


def pick_boost_keywords(
    summaries: list[dict], query: str, cap: int = MAX_NEW_TERMS
) -> list[str]:
    """Union keywords across all summaries, drop ones already in the query,
    rank by (cross-paper frequency desc, length desc), return top `cap`."""
    query_tokens = _query_token_set(query)
    freq: Counter[str] = Counter()
    first_seen: dict[str, int] = {}
    for i, s in enumerate(summaries):
        for kw in (s.get("keywords") or []):
            kw = kw.strip().lower()
            if not kw:
                continue
            if _kw_already_in_query(kw, query_tokens):
                continue
            if kw not in first_seen:
                first_seen[kw] = i
            freq[kw] += 1

    ranked = sorted(
        freq.keys(),
        key=lambda k: (-freq[k], -len(k), first_seen[k]),
    )
    return ranked[:cap]


def run_paper_search(query: str, top: int = 10) -> dict:
    """Invoke paper-search via uv run, return parsed JSON payload."""
    cmd = [
        "uv", "run", "--directory", str(PAPER_SEARCH_DIR), "paper-search",
        query, "--top", str(top), "-f", "json",
    ]
    print(f"$ paper-search {query!r} --top {top}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode not in (0, 4):
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"paper-search exited {proc.returncode}")
    return json.loads(proc.stdout)


def run_paper_summarize(paper_ref: str) -> dict | None:
    """Invoke paper-summarize via uv run, return parsed JSON payload or None on failure."""
    if not PAPER_SUMMARIZE_DIR.exists():
        return None
    cmd = [
        "uv", "run", "--directory", str(PAPER_SUMMARIZE_DIR), "paper-summarize",
        paper_ref, "-f", "json",
    ]
    print(f"$ paper-summarize {paper_ref!r}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(f"  ! summarize failed ({proc.returncode}): {proc.stderr.strip()[:200]}\n")
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"  ! summarize returned non-JSON: {e}\n")
        return None


def _paper_key(p: dict) -> str:
    """Stable identity for dedup across passes."""
    aid = p.get("arxiv_id")
    if aid:
        return f"arxiv:{aid}"
    doi = p.get("doi")
    if doi:
        return f"doi:{doi}"
    title = (p.get("title") or "").lower()
    return f"title:{re.sub(r'[^a-z0-9]+', '', title)[:50]}"


def _best_ref_for_summarize(p: dict) -> str | None:
    """Prefer arxiv_id for speed (direct PDF fetch), then DOI, then URL."""
    return p.get("arxiv_id") or p.get("doi") or p.get("url")


def check_summarize_available() -> bool:
    if not PAPER_SUMMARIZE_DIR.exists():
        print("paper-summarize not found in this workspace — running pass 1 only.")
        return False
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY unset — running pass 1 only.")
        return False
    proc = subprocess.run(
        ["uv", "run", "--directory", str(PAPER_SUMMARIZE_DIR), "paper-summarize", "--help"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(f"paper-summarize --help exited {proc.returncode} — running pass 1 only.")
        return False
    return True


def main() -> int:
    print(f"Query: {QUERY!r}")
    print(f"Workspace: {BUNDLE_DIR}\n")

    print("=== Pass 1: initial search ===")
    pass1 = run_paper_search(QUERY, top=10)
    pass1_papers = pass1.get("papers") or []
    pass1_keys = {_paper_key(p) for p in pass1_papers}
    print(f"  got {len(pass1_papers)} papers")
    for i, p in enumerate(pass1_papers[:5], 1):
        print(f"   {i}. [{p.get('score', 0):.2f}] {p.get('title')}")

    if not check_summarize_available():
        return 0

    print("\n=== Summarizing top hits ===")
    summaries: list[dict] = []
    for p in pass1_papers[:TOP_K_TO_SUMMARIZE]:
        ref = _best_ref_for_summarize(p)
        if not ref:
            continue
        s = run_paper_summarize(ref)
        if s is not None:
            summaries.append(s)

    if not summaries:
        print("No summaries completed — cannot compute keyword boost. Stopping.")
        return 1

    print(f"\nCollected {len(summaries)} summary/summaries.")
    for i, s in enumerate(summaries, 1):
        kws = s.get("keywords") or []
        print(f"  paper {i}: keywords = {kws}")

    new_terms = pick_boost_keywords(summaries, QUERY, cap=MAX_NEW_TERMS)
    print(f"\nBoost terms (after dedup + cap): {new_terms}")

    if not new_terms:
        print("No new keywords to add — the first query already covered them.")
        return 0

    enriched = QUERY + " " + " ".join(new_terms)
    print(f"\n=== Pass 2: re-search with boosted query ===")
    print(f"Enriched query: {enriched!r}")
    pass2 = run_paper_search(enriched, top=10)
    pass2_papers = pass2.get("papers") or []

    delta = [p for p in pass2_papers if _paper_key(p) not in pass1_keys]
    print(f"\nSecond pass added {len(delta)} papers using keywords: "
          f"{', '.join(new_terms)}")
    if not delta:
        print("  (no new recall — first pass already had everything)")
        return 0

    for i, p in enumerate(delta, 1):
        sc = p.get("score")
        sc_s = f"{sc:.2f}" if sc is not None else "—"
        cites = p.get("citation_count")
        cites_s = f"{cites:,} cites" if cites else "cites unknown"
        print(f"  {i}. [{sc_s}] {p.get('title')}  ({cites_s}, year {p.get('year')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

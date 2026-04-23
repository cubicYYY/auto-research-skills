"""Live example: hit arXiv + OpenAlex + Semantic Scholar for 'attention'.

Expected behavior:
  - "Attention Is All You Need" lands at #1.
  - FlashAttention and sparse-attention variants appear in the top results.

Run:
    uv run python examples/attention_live.py

Takes ~1–4 minutes depending on source latency. Requires network.
"""
from __future__ import annotations

import asyncio

from paper_search.core import run_search
from paper_search.sources import REGISTRY


async def main() -> None:
    sources = [REGISTRY[n]() for n in ("arxiv", "openalex", "semantic_scholar")]
    result = await run_search(
        sources,
        query="attention",
        year_from=2015,
        year_to=2026,
        per_source=50,
        top=20,
    )

    print(
        f"Found {result.total_candidates} candidates across "
        f"{len(result.sources_used)} sources ({', '.join(result.sources_used)})."
    )
    print("-" * 72)
    for i, p in enumerate(result.papers, 1):
        cites = f"{p.citation_count:,}" if p.citation_count else "—"
        srcs = ", ".join(p.sources)
        print(f" {i:>2}. [{p.score:.3f}] {p.title}")
        print(f"     cites={cites}  year={p.year}  sources=[{srcs}]")

    if result.errors:
        print("\nErrors:")
        for e in result.errors:
            print(f"  {e['source']}: {e['error']}")

    top_title = result.papers[0].title.lower().replace("'", "")
    assert "attention is all you need" in top_title, \
        f"expected Vaswani at top, got: {result.papers[0].title}"
    all_titles = " || ".join(p.title.lower() for p in result.papers)
    assert "flashattention" in all_titles or "flash attention" in all_titles, \
        "expected flash attention variant in top 20"
    assert "sparse" in all_titles or "longformer" in all_titles, \
        "expected sparse-attention variant in top 20"
    print("\nAll checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
